"""
メインアプリケーション
FastAPI + LangChain + Ollama + MCP統合

クライアントからBase64資料を受け取り、AIでレビューして結果を返す
"""
import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_ollama import ChatOllama
from pydantic import BaseModel

# MCPクライアントをインポート
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_client.client import MCPClient


# グローバルMCPクライアント
mcp_client: MCPClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリのライフサイクル管理"""
    global mcp_client
    # MCPサーバー起動
    mcp_client = MCPClient(["python", "mcp_server/server.py"])
    mcp_client.start()
    print("MCP Server started")

    yield

    # MCPサーバー停止
    if mcp_client:
        mcp_client.stop()
        print("MCP Server stopped")


app = FastAPI(
    title="Document Review API",
    description="Base64資料をAIでレビューするAPI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewRequest(BaseModel):
    """レビューリクエスト"""

    base64_content: str
    filename: str
    document_type: str = "general"


class ReviewResponse(BaseModel):
    """レビューレスポンス"""

    filename: str
    document_type: str
    review: str
    prompt_used: str


def get_llm() -> ChatOllama:
    """Ollama LLMインスタンスを取得"""
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.7,
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    """フロントエンドHTMLを返す"""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "index.html")
    with open(html_path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
async def health():
    """ヘルスチェック"""
    return {"status": "ok", "mcp_server": mcp_client is not None}


@app.get("/api/tools")
async def list_tools():
    """利用可能なMCPツール一覧"""
    if not mcp_client:
        raise HTTPException(status_code=500, detail="MCP server not running")
    return {"tools": mcp_client.list_tools()}


@app.post("/api/analyze-type")
async def analyze_type(request: ReviewRequest):
    """資料タイプを分析"""
    if not mcp_client:
        raise HTTPException(status_code=500, detail="MCP server not running")

    result = mcp_client.analyze_document_type(request.filename, request.base64_content)
    return result


@app.post("/api/review", response_model=ReviewResponse)
async def review_document(request: ReviewRequest):
    """
    Base64資料をAIでレビュー

    1. MCPサーバーからレビュープロンプトを取得
    2. Ollama (LLM)でレビューを実行
    3. 結果を返す
    """
    if not mcp_client:
        raise HTTPException(status_code=500, detail="MCP server not running")

    try:
        # MCPサーバーからレビュープロンプトを取得
        mcp_result = mcp_client.review_document(
            request.base64_content, request.document_type, request.filename
        )

        prompt = mcp_result.get("prompt", "")

        if not prompt:
            raise HTTPException(status_code=500, detail="Failed to get review prompt from MCP server")

        # LangChain + Ollamaでレビュー実行
        llm = get_llm()
        response = llm.invoke(prompt)

        return ReviewResponse(
            filename=request.filename,
            document_type=request.document_type,
            review=response.content,
            prompt_used=prompt[:500] + "..." if len(prompt) > 500 else prompt,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-and-review")
async def upload_and_review(file: UploadFile, document_type: str = "general"):
    """
    ファイルをアップロードしてレビュー（マルチパートフォーム用）
    サーバー側でBase64変換を行う
    """
    import base64

    if not mcp_client:
        raise HTTPException(status_code=500, detail="MCP server not running")

    try:
        # ファイル読み込み & Base64変換
        content = await file.read()
        base64_content = base64.b64encode(content).decode("utf-8")

        # 資料タイプを自動判定（指定がない場合）
        if document_type == "auto":
            type_result = mcp_client.analyze_document_type(file.filename or "unknown", base64_content)
            document_type = type_result.get("suggested_type", "general")

        # MCPサーバーからレビュープロンプトを取得
        mcp_result = mcp_client.review_document(base64_content, document_type, file.filename or "unknown")

        prompt = mcp_result.get("prompt", "")

        if not prompt:
            raise HTTPException(status_code=500, detail="Failed to get review prompt from MCP server")

        # LangChain + Ollamaでレビュー実行
        llm = get_llm()
        response = llm.invoke(prompt)

        return {
            "filename": file.filename,
            "document_type": document_type,
            "review": response.content,
            "content_length": len(content),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
