"""
Ollama CLIエージェント + MCP統合

Claude Codeライクな対話型AIエージェント
Ollamaがツール呼び出しを判断してMCPサーバーと連携
"""
import os
import sys
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_ollama import ChatOllama

# MCPクライアントをインポート
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_client.client import MCPClient


class MCPAgentCLI:
    """MCP統合CLIエージェント"""

    def __init__(self, model: str = "llama3.2"):
        self.model = model
        self.mcp_client: MCPClient | None = None
        self.agent_executor: AgentExecutor | None = None
        self.chat_history: list = []

    def start(self):
        """エージェント起動"""
        print(f"🚀 Ollama Agent starting... (model: {self.model})")

        # MCPサーバー起動
        mcp_server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mcp_server",
            "server.py",
        )
        self.mcp_client = MCPClient(["python", mcp_server_path])
        self.mcp_client.start()
        print("✅ MCP Server connected")

        # LangChainエージェント構築
        self._build_agent()
        print("✅ Agent ready\n")

    def stop(self):
        """エージェント停止"""
        if self.mcp_client:
            self.mcp_client.stop()
            print("\n👋 Agent stopped")

    def _build_agent(self):
        """LangChainエージェント構築"""
        # Ollama LLM
        llm = ChatOllama(
            model=self.model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0.7,
        )

        # MCPツールをLangChainツールにラップ
        tools = self._wrap_mcp_tools()

        # プロンプト
        prompt = ChatPromptTemplate.from_messages([
            ("system", """あなたは資料レビューを支援するAIアシスタントです。

ユーザーが資料のレビューを依頼したら、適切なツールを使ってレビューを行います。
利用可能なツール:
- review_document: 資料をレビューしてフィードバックを生成
- analyze_document_type: 資料のタイプを分析

日本語で応答してください。"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # エージェント作成
        agent = create_tool_calling_agent(llm, tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
        )

    def _wrap_mcp_tools(self) -> list[Tool]:
        """MCPツールをLangChainツールにラップ"""
        tools = []

        # review_document ツール
        def review_document(input_str: str) -> str:
            """資料をレビューする。引数: 'base64_content|document_type|filename' 形式"""
            try:
                parts = input_str.split("|")
                if len(parts) >= 3:
                    base64_content, doc_type, filename = parts[0], parts[1], parts[2]
                else:
                    return "エラー: 引数は 'base64_content|document_type|filename' 形式で指定してください"

                result = self.mcp_client.review_document(base64_content, doc_type, filename)
                return result.get("prompt", "レビュープロンプトの生成に失敗しました")
            except Exception as e:
                return f"エラー: {e}"

        tools.append(Tool(
            name="review_document",
            description="資料をレビューしてフィードバックを生成します。引数: 'base64_content|document_type|filename' 形式（例: 'SGVsbG8=|technical|spec.md'）",
            func=review_document,
        ))

        # analyze_document_type ツール
        def analyze_document_type(input_str: str) -> str:
            """資料タイプを分析する。引数: 'filename|base64_content' 形式"""
            try:
                parts = input_str.split("|")
                if len(parts) >= 2:
                    filename, base64_content = parts[0], parts[1]
                else:
                    return "エラー: 引数は 'filename|base64_content' 形式で指定してください"

                result = self.mcp_client.analyze_document_type(filename, base64_content)
                return f"資料タイプ: {result.get('suggested_type', 'unknown')}"
            except Exception as e:
                return f"エラー: {e}"

        tools.append(Tool(
            name="analyze_document_type",
            description="資料のタイプ（technical/business/design/general）を分析します。引数: 'filename|base64_content' 形式",
            func=analyze_document_type,
        ))

        # ファイル読み込みツール（便利機能）
        def read_file(filepath: str) -> str:
            """ローカルファイルを読み込んでBase64変換"""
            import base64
            try:
                filepath = filepath.strip()
                if not os.path.exists(filepath):
                    return f"エラー: ファイルが見つかりません: {filepath}"

                with open(filepath, "rb") as f:
                    content = f.read()

                base64_content = base64.b64encode(content).decode("utf-8")
                filename = os.path.basename(filepath)
                return f"ファイル読み込み完了: {filename}\nBase64 (先頭100文字): {base64_content[:100]}...\n\nこのBase64コンテンツを review_document ツールで使用できます。"
            except Exception as e:
                return f"エラー: {e}"

        tools.append(Tool(
            name="read_file",
            description="ローカルファイルを読み込んでBase64に変換します。引数: ファイルパス",
            func=read_file,
        ))

        return tools

    def chat(self, user_input: str) -> str:
        """ユーザー入力を処理"""
        if not self.agent_executor:
            return "エージェントが初期化されていません"

        try:
            result = self.agent_executor.invoke({
                "input": user_input,
                "chat_history": self.chat_history,
            })

            # 履歴に追加
            self.chat_history.append(("human", user_input))
            self.chat_history.append(("ai", result["output"]))

            return result["output"]
        except Exception as e:
            return f"エラーが発生しました: {e}"

    def run(self):
        """対話ループ"""
        self.start()

        print("=" * 50)
        print("📄 Document Review Agent")
        print("=" * 50)
        print("コマンド:")
        print("  /quit - 終了")
        print("  /clear - 履歴クリア")
        print("  /file <path> - ファイルをレビュー")
        print("=" * 50)
        print()

        try:
            while True:
                try:
                    user_input = input("You> ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                # コマンド処理
                if user_input == "/quit":
                    break
                elif user_input == "/clear":
                    self.chat_history = []
                    print("履歴をクリアしました\n")
                    continue
                elif user_input.startswith("/file "):
                    filepath = user_input[6:].strip()
                    user_input = f"ファイル {filepath} を読み込んでレビューしてください"

                # エージェント実行
                print("\nAgent> ", end="", flush=True)
                response = self.chat(user_input)
                print(response)
                print()

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="Ollama CLI Agent with MCP")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name")
    args = parser.parse_args()

    agent = MCPAgentCLI(model=args.model)
    agent.run()


if __name__ == "__main__":
    main()
