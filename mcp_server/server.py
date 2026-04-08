"""
MCP Server - 資料レビューサーバー
Base64エンコードされた資料を受け取り、AIレビュー用のプロンプトを生成
または、Ollama (LLM) を使って直接レビューを実行
"""
import json
import sys
import base64
import os
from typing import Any

import requests


class MCPServer:
    """MCPサーバー - 資料レビュー機能を提供"""

    def __init__(self):
        self.tools = {
            "review_document": self.review_document,
            "analyze_document_type": self.analyze_document_type,
            "execute_review": self.execute_review,
        }
        self.prompts = {
            "document_review": self.get_document_review_prompt,
        }
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "gemma4")

    def review_document(
        self, base64_content: str, document_type: str = "general", filename: str = ""
    ) -> dict[str, Any]:
        """
        Base64エンコードされた資料をレビューするためのプロンプトを生成

        Args:
            base64_content: Base64エンコードされた資料内容
            document_type: 資料タイプ (technical, business, design, general)
            filename: ファイル名
        """
        # Base64をデコードしてテキストを取得
        try:
            decoded_content = base64.b64decode(base64_content).decode("utf-8")
        except Exception:
            # バイナリファイルの場合はBase64のまま処理
            decoded_content = f"[Binary file: {filename}]"

        review_prompts = {
            "technical": f"""
あなたは技術文書のレビュアーです。以下の資料をレビューしてください。

## レビュー観点
1. 技術的正確性
2. コードの品質（コードが含まれる場合）
3. セキュリティ上の問題
4. パフォーマンスの考慮
5. ベストプラクティスへの準拠

## 資料内容
ファイル名: {filename}
---
{decoded_content}
---

## 出力形式
以下の形式でレビュー結果を出力してください：
- 概要: 資料の概要
- 良い点: 評価できる点
- 改善点: 改善が必要な点（優先度付き）
- 推奨事項: 具体的なアクション
""",
            "business": f"""
あなたはビジネス文書のレビュアーです。以下の資料をレビューしてください。

## レビュー観点
1. ビジネス目標との整合性
2. 論理構成の明確さ
3. 実現可能性
4. リスク分析
5. ROI/コスト効率

## 資料内容
ファイル名: {filename}
---
{decoded_content}
---

## 出力形式
以下の形式でレビュー結果を出力してください：
- エグゼクティブサマリー
- 強み
- 課題・リスク
- 推奨アクション
""",
            "design": f"""
あなたはデザインドキュメントのレビュアーです。以下の資料をレビューしてください。

## レビュー観点
1. ユーザビリティ
2. アクセシビリティ
3. 一貫性
4. スケーラビリティ
5. メンテナンス性

## 資料内容
ファイル名: {filename}
---
{decoded_content}
---

## 出力形式
以下の形式でレビュー結果を出力してください：
- デザイン概要
- UX評価
- 改善提案
- 優先度付きアクションリスト
""",
            "general": f"""
あなたは文書レビュアーです。以下の資料を総合的にレビューしてください。

## レビュー観点
1. 内容の正確性
2. 構成の明確さ
3. 読みやすさ
4. 完成度
5. 改善の余地

## 資料内容
ファイル名: {filename}
---
{decoded_content}
---

## 出力形式
以下の形式でレビュー結果を出力してください：
- 概要
- 評価ポイント
- 改善提案
- 総合評価
""",
        }

        prompt = review_prompts.get(document_type, review_prompts["general"])

        return {
            "prompt": prompt,
            "document_type": document_type,
            "filename": filename,
            "content_length": len(decoded_content),
        }

    def analyze_document_type(self, filename: str, base64_content: str) -> dict[str, Any]:
        """ファイル名と内容から資料タイプを推測"""
        extension = filename.split(".")[-1].lower() if "." in filename else ""

        type_mapping = {
            "py": "technical",
            "js": "technical",
            "ts": "technical",
            "java": "technical",
            "go": "technical",
            "rs": "technical",
            "md": "general",
            "txt": "general",
            "pdf": "general",
            "doc": "business",
            "docx": "business",
            "pptx": "business",
            "xls": "business",
            "xlsx": "business",
            "fig": "design",
            "sketch": "design",
            "psd": "design",
        }

        suggested_type = type_mapping.get(extension, "general")

        return {
            "filename": filename,
            "extension": extension,
            "suggested_type": suggested_type,
        }

    def execute_review(
        self, base64_content: str, document_type: str = "general", filename: str = ""
    ) -> dict[str, Any]:
        """
        Base64資料をOllama (LLM) で直接レビューして結果を返す

        Args:
            base64_content: Base64エンコードされた資料内容
            document_type: 資料タイプ (technical, business, design, general)
            filename: ファイル名
        """
        # まずプロンプトを生成
        prompt_result = self.review_document(base64_content, document_type, filename)
        prompt = prompt_result.get("prompt", "")

        if not prompt:
            return {
                "success": False,
                "error": "プロンプト生成に失敗しました",
                "review": None,
            }

        # Ollamaでレビュー実行
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "filename": filename,
                "document_type": document_type,
                "review": result.get("response", ""),
                "model": self.ollama_model,
            }

        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": f"Ollamaに接続できません ({self.ollama_base_url})",
                "review": None,
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Ollamaからの応答がタイムアウトしました",
                "review": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "review": None,
            }

    def get_document_review_prompt(self) -> dict[str, Any]:
        """資料レビュー用のプロンプトテンプレートを返す"""
        return {
            "name": "document_review",
            "description": "資料レビュー用プロンプト",
            "template": """
あなたは資料レビューの専門家です。
アップロードされた資料を詳細にレビューし、建設的なフィードバックを提供してください。
""",
        }

    def handle_request(self, request: dict) -> dict:
        """MCPリクエストを処理"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "prompts": {"listChanged": True},
                    },
                    "serverInfo": {"name": "document-review-server", "version": "1.0.0"},
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "review_document",
                            "description": "Base64エンコードされた資料をレビュー",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "base64_content": {
                                        "type": "string",
                                        "description": "Base64エンコードされた資料",
                                    },
                                    "document_type": {
                                        "type": "string",
                                        "enum": ["technical", "business", "design", "general"],
                                        "description": "資料タイプ",
                                    },
                                    "filename": {"type": "string", "description": "ファイル名"},
                                },
                                "required": ["base64_content"],
                            },
                        },
                        {
                            "name": "analyze_document_type",
                            "description": "ファイルから資料タイプを推測",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string", "description": "ファイル名"},
                                    "base64_content": {
                                        "type": "string",
                                        "description": "Base64エンコードされた資料",
                                    },
                                },
                                "required": ["filename", "base64_content"],
                            },
                        },
                        {
                            "name": "execute_review",
                            "description": "Base64資料をOllama (LLM) で直接レビューして結果を返す",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "base64_content": {
                                        "type": "string",
                                        "description": "Base64エンコードされた資料",
                                    },
                                    "document_type": {
                                        "type": "string",
                                        "enum": ["technical", "business", "design", "general"],
                                        "description": "資料タイプ",
                                    },
                                    "filename": {"type": "string", "description": "ファイル名"},
                                },
                                "required": ["base64_content"],
                            },
                        },
                    ]
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name in self.tools:
                result = self.tools[tool_name](**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
                }

        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "prompts": [
                        {
                            "name": "document_review",
                            "description": "資料レビュー用プロンプト",
                        }
                    ]
                },
            }

        elif method == "prompts/get":
            prompt_name = params.get("name")
            if prompt_name in self.prompts:
                result = self.prompts[prompt_name]()
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result,
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"},
        }

    def run(self):
        """stdin/stdoutでMCPサーバーを実行"""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)},
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    server = MCPServer()
    server.run()
