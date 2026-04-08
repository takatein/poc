"""
MCP Client - MCPサーバーと通信するクライアント
"""
import json
import subprocess
from typing import Any


class MCPClient:
    """MCPクライアント - サーバーとstdin/stdoutで通信"""

    def __init__(self, server_command: list[str]):
        self.server_command = server_command
        self.process: subprocess.Popen | None = None
        self.request_id = 0

    def start(self) -> dict:
        """MCPサーバーを起動して初期化"""
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return self._send_request("initialize", {"protocolVersion": "2024-11-05"})

    def stop(self):
        """MCPサーバーを停止"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def _send_request(self, method: str, params: dict | None = None) -> dict:
        """リクエストを送信してレスポンスを受信"""
        if not self.process:
            raise RuntimeError("Server not started")

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        response_line = self.process.stdout.readline()
        return json.loads(response_line)

    def list_tools(self) -> list[dict]:
        """利用可能なツール一覧を取得"""
        response = self._send_request("tools/list")
        return response.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """ツールを呼び出す"""
        response = self._send_request("tools/call", {"name": name, "arguments": arguments})
        return response.get("result", {})

    def list_prompts(self) -> list[dict]:
        """利用可能なプロンプト一覧を取得"""
        response = self._send_request("prompts/list")
        return response.get("result", {}).get("prompts", [])

    def get_prompt(self, name: str) -> dict:
        """プロンプトを取得"""
        response = self._send_request("prompts/get", {"name": name})
        return response.get("result", {})

    def review_document(
        self, base64_content: str, document_type: str = "general", filename: str = ""
    ) -> dict[str, Any]:
        """資料をレビュー（便利メソッド）"""
        result = self.call_tool(
            "review_document",
            {
                "base64_content": base64_content,
                "document_type": document_type,
                "filename": filename,
            },
        )

        # レスポンスからテキストを抽出
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result

    def analyze_document_type(self, filename: str, base64_content: str) -> dict[str, Any]:
        """資料タイプを分析（便利メソッド）"""
        result = self.call_tool(
            "analyze_document_type",
            {"filename": filename, "base64_content": base64_content},
        )

        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result


def main():
    """テスト実行"""
    import base64

    # テスト用のサンプルコンテンツ
    sample_content = """
# サンプルドキュメント

これはテスト用の資料です。

## 概要
- ポイント1
- ポイント2
- ポイント3
"""
    base64_content = base64.b64encode(sample_content.encode()).decode()

    # MCPクライアントを起動
    client = MCPClient(["python", "mcp_server/server.py"])

    try:
        print("サーバー初期化...")
        init_result = client.start()
        print(f"初期化結果: {json.dumps(init_result, indent=2, ensure_ascii=False)}")

        print("\nツール一覧取得...")
        tools = client.list_tools()
        print(f"利用可能なツール: {json.dumps(tools, indent=2, ensure_ascii=False)}")

        print("\n資料タイプ分析...")
        type_result = client.analyze_document_type("test.md", base64_content)
        print(f"分析結果: {json.dumps(type_result, indent=2, ensure_ascii=False)}")

        print("\n資料レビュー...")
        review_result = client.review_document(base64_content, "general", "test.md")
        print(f"レビュー結果: {json.dumps(review_result, indent=2, ensure_ascii=False)}")

    finally:
        client.stop()
        print("\nサーバー停止")


if __name__ == "__main__":
    main()
