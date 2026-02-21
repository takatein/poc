# AWS Google Auth PoC

AWS Cognito + Google OAuth でログインが正常に動作することを確認するための最小構成 PoC。

## アーキテクチャ

```
[React App (localhost:3000)]
        │
        │ signInWithRedirect("Google")
        ▼
[Cognito Hosted UI]
        │
        │ Google OAuth redirect
        ▼
[Google OAuth 2.0]
        │
        │ Authorization Code
        ▼
[Cognito Callback → Token交換]
        │
        │ ID Token / Access Token
        ▼
[React App ログイン完了]
```

## 前提条件

- Node.js 18+
- AWS CLI（設定済み）
- AWS CDK CLI（`npm install -g aws-cdk`）
- Google Cloud Console で OAuth 2.0 クレデンシャルを作成済み

## セットアップ手順

### Step 1: Google Cloud Console で OAuth クレデンシャル作成

1. [Google Cloud Console](https://console.cloud.google.com/) → APIとサービス → 認証情報
2. **OAuth 2.0 クライアント ID** を作成
   - アプリケーションの種類: **ウェブアプリケーション**
   - 承認済みの JavaScript 生成元: （空でOK）
   - 承認済みのリダイレクト URI: **CDKデプロイ後に設定**（後述）
3. **クライアント ID** と **クライアント シークレット** をメモ

### Step 2: AWS にインフラをデプロイ

```bash
# インフラの依存関係インストール
cd infra && npm install && cd ..

# CDK デプロイ（Google クレデンシャルを渡す）
cd infra
npx cdk deploy \
  -c googleClientId="YOUR_GOOGLE_CLIENT_ID" \
  -c googleClientSecret="YOUR_GOOGLE_CLIENT_SECRET"
```

デプロイ成功後、以下が出力されます：
- `UserPoolId`
- `UserPoolClientId`
- `CognitoDomain`

### Step 3: Google Cloud Console にリダイレクト URI を追加

CDK の出力で得た `CognitoDomain` を使って、Google Cloud Console の OAuth クライアントに以下を追加：

- 承認済みのリダイレクト URI: `https://{CognitoDomain}/oauth2/idpresponse`

### Step 4: フロントエンドを起動

```bash
# ルートに戻る
cd ..

# 依存関係インストール
npm install

# .env を作成（CDK出力値を設定）
cp .env.example .env
# .env を編集して CDK 出力の値を入力

# 開発サーバー起動
npm run dev
```

### Step 5: 動作確認

1. `http://localhost:3000` をブラウザで開く
2. 「Google でログイン」ボタンをクリック
3. Google アカウントを選択・認証
4. `http://localhost:3000/` にリダイレクトされ、ユーザー情報が表示されれば成功！

## リダイレクトループのトラブルシューティング

リダイレクトループが発生する主な原因：

| 原因 | 対策 |
|------|------|
| **callbackUrl の不一致** | Cognito App Client、Amplify設定、実際のURLの3箇所が完全一致すること（末尾 `/` 含む） |
| **responseType の不一致** | `code`（Authorization Code + PKCE）を使用。`token`（Implicit）だと問題が起きやすい |
| **Cookie / セッションの競合** | ブラウザの Cookie をクリアして再試行 |
| **複数の認証ライブラリの干渉** | Amplify のみ使用し、他の認証ライブラリを混在させない |
| **Hosted UI Domain の設定ミス** | `https://` プレフィックスを付けない（Amplify v6 ではドメイン名のみ） |

## クリーンアップ

```bash
cd infra
npx cdk destroy
```

## ファイル構成

```
.
├── index.html              # Vite エントリポイント
├── package.json            # フロントエンド依存関係
├── tsconfig.json
├── vite.config.ts
├── .env.example            # 環境変数テンプレート
├── src/
│   ├── main.tsx            # React エントリ + Amplify初期化
│   ├── amplify-config.ts   # Amplify Auth 設定
│   ├── App.tsx             # メイン画面（ログイン/ログアウト）
│   └── vite-env.d.ts       # 型定義
└── infra/                  # AWS CDK
    ├── bin/app.ts          # CDK アプリエントリ
    ├── lib/google-auth-stack.ts  # Cognito + Google IdP定義
    ├── cdk.json
    ├── package.json
    └── tsconfig.json
```
