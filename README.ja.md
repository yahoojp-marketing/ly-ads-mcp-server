# LY Ads MCP Server

[English](README.md)

LY Ads MCP Server は、 [Model Context Protocol （ MCP ） ](https://modelcontextprotocol.io/) を通じて [LINEヤフー広告 API](https://ads-developers.yahoo.co.jp/ja/ads-api/) を利用するためのローカルサーバーです。
MCP に対応した AI エージェントから、LINEヤフー広告のディスプレイ広告及び検索広告のアカウント、キャンペーン、広告などを参照できます。

このサーバーは Streamable HTTP で動作し、 LINEヤフー広告の OAuth 認証には [FastMCP OAuth Proxy](https://gofastmcp.com/servers/auth/oauth-proxy) を使用します。

## 提供するツール

### ディスプレイ広告

| ツール | 説明 |
|---|---|
| `list_accessible_display_base_accounts` | 認可したユーザーが利用できるベースアカウントを取得します。 |
| `list_accessible_display_accounts` | ベースアカウント配下の広告アカウントを取得します。 |
| `list_display_campaigns` | 広告アカウントのキャンペーンを取得します。 |
| `list_display_labels` | 広告アカウントのラベルを取得します。 |
| `list_display_ad_groups` | 広告アカウントの広告グループを取得します。 |
| `list_display_ad_group_targets` | 広告グループのターゲティング設定を取得します。 |
| `list_display_ads` | 広告アカウントの広告を取得します。 |
| `get_display_report_fields` | レポート種別で利用できるフィールドを取得します。 |
| `read_display_report` | 指定した条件でレポートを作成し、先頭 50 件のプレビューと全件 CSV の保存先を返します。 |

### 検索広告

| ツール | 説明 |
|---|---|
| `list_accessible_search_base_accounts` | 認可したユーザーが利用できるベースアカウントを取得します。 |
| `list_accessible_search_accounts` | ベースアカウント配下の広告アカウントを取得します。 |
| `list_search_campaigns` | 広告アカウントのキャンペーンを取得します。 |
| `list_search_labels` | 広告アカウントのラベルを取得します。 |
| `list_search_campaign_targets` | キャンペーンのターゲティング設定を取得します。 |
| `list_search_campaign_negative_keywords` | キャンペーンに設定した除外キーワードを取得します。 |
| `list_search_ad_groups` | 広告アカウントの広告グループを取得します。 |
| `list_search_ad_group_keywords` | 広告グループに設定したキーワードを取得します。 |
| `list_search_ads` | 広告アカウントの広告を取得します。 |
| `get_search_report_fields` | レポート種別で利用できるフィールドを取得します。 |
| `read_search_report` | 指定した条件でレポートを作成し、先頭 50 件のプレビューと全件 CSV の保存先を返します。 |

MCP クライアントには、ディスプレイ広告のツールが `ly_ads_display` 、検索広告のツールが `ly_ads_search` の名前空間付きで公開されます。
一覧ツールは結果をページ単位で返します。

### read_display_report, read_search_report の利用に関する補足

レポートを依頼するときは、広告種別、対象アカウント、対象期間、確認したい指標や集計単位を指定してください。
API のフィールド名を調べて指定する必要はありません。
AI エージェントがレポート種別に対応する項目を確認し、API が返すフィールド情報に基づいて組み合わせを選択します。

```text
ベースアカウント ID 123456、アカウント ID 789012 の検索広告について、
2026 年 8 月のキャンペーン別クリック数、コンバージョン数、コストを取得してください。
```

ディスプレイ広告のリーチ、コンバージョン経路、キャンペーン横断リーチ、アトリビューションモデル比較など、一部のレポートには専用の条件があります。
依頼内容だけでは条件を決められない場合、AI エージェントが必要な情報を確認します。
検索広告でも、レポート種別によって期間指定の要否が異なります。

取得結果には先頭 50 件のプレビューが含まれます。
プレビューで省略された行を含むレポート全体は、UTF-8 の CSV ファイルとして、`LY_ADS_REPORT_OUTPUT_DIR` で指定したディレクトリの `display/YYYY-MM-DD` または `search/YYYY-MM-DD` に保存されます。
返されるパスはサーバーを実行しているマシン上のローカルファイルパスであり、MCP Resource ではありません。
MCP クライアントにはこのパスの読み取り権限が必要であり、リモート環境やサンドボックス環境のクライアントからはファイルを参照できない場合があります。
CSV ファイルは自動では削除されません。

レポートの作成が 60 秒以内に完了しない場合はエラーになります。
その場合は、対象期間、取得項目、フィルターを絞って再度依頼してください。

## 利用前の準備

利用開始までに、 LINEヤフー広告 API の利用申し込みと MCP 用 OAuth クライアントの発行が必要です。

1. [LINEヤフー広告 API のお申し込み手順 ](https://ads-developers.yahoo.co.jp/ja/ads-api/startup-guide/apply-api-use.html) に従い、 LINEヤフー広告 API の利用を申し込みます。
2. 申し込み完了後、 [LINEヤフービジネス ID の MCP 用 OAuth クライアント発行画面 ](https://connect-business.yahoo.co.jp/client/mcp) を開きます。
3. MCP 用 OAuth クライアントを発行します。
4. 発行されたクライアント ID とクライアントシークレットを取得します。
    * 通常の API アプリケーションは企業単位で管理されますが、MCP 用 OAuth クライアントはビジネス ID 単位で管理されます。

OAuth クライアントの情報は、このサーバーを起動するために使用します。
アクセストークンとリフレッシュトークンは FastMCP OAuth Proxy が管理するため、 MCP クライアントへ直接設定する必要はありません。

MCP 用 OAuth クライアント発行画面へアクセスするためには、API 管理ツールの管理権限もしくは利用権限が必要です。
API 管理ツールの権限管理については、以下のヘルプをご確認ください。

* [LINEヤフー広告 API 管理ツールの管理者を追加したいです。 - LINEヤフー広告 API | Developer Center](https://ads-developers.yahoo.co.jp/ja/ads-api/faq/faq.html)

## セットアップ

Python 3.11 以降、[pipx](https://pipx.pypa.io/stable/installation/)、Git を用意してください。

発行した OAuth クライアントの情報と JWT 署名キーを、サーバーを起動するシェルの環境変数に設定します。

```bash
export LY_ADS_CLIENT_ID="発行されたクライアント ID"
export LY_ADS_CLIENT_SECRET="発行されたクライアントシークレット"
export LY_ADS_MCP_JWT_SIGNING_KEY="生成した JWT 署名キー"
export LY_ADS_REPORT_OUTPUT_DIR="$HOME/.ly-ads-mcp/reports"
```

これらの値を Git の管理対象に含めず、ほかの利用者から読み取られないように管理してください。

### 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `LY_ADS_CLIENT_ID` | はい | MCP 用 OAuth クライアントのクライアント ID です。 |
| `LY_ADS_CLIENT_SECRET` | はい | MCP 用 OAuth クライアントのクライアントシークレットです。 |
| `LY_ADS_MCP_JWT_SIGNING_KEY` | はい | FastMCP が発行する JWT の署名キーです。OAuth クライアントシークレットとは異なるランダム値を設定します。 |
| `LY_ADS_REPORT_OUTPUT_DIR` | いいえ | レポート CSV の保存先ディレクトリです。未指定の場合は、サーバーを起動したディレクトリの `reports` に保存します。 |

### JWT 署名キーの生成

JWT 署名キーは OAuth クライアントシークレットとは別に生成し、同じ値を再利用しないでください。
次のコマンドで 256 ビットのランダム値を生成できます。

```bash
openssl rand -base64 32
```

生成した値を `LY_ADS_MCP_JWT_SIGNING_KEY` に設定します。
設定値には最低 32 文字が必要ですが、文字数だけではランダム性を保証できないため、上記のような暗号学的に安全な乱数生成方法を使用してください。

## サーバーの起動

次のコマンドでバージョンを指定してサーバーを起動します。

```bash
pipx run \
  --spec "git+https://github.com/yahoojp-marketing/ly-ads-mcp-server.git@v0.0.1" \
  ly-ads-mcp
```

サーバーは `http://localhost:18765/mcp` で MCP クライアントからの接続を受け付けます。

## MCP クライアントの設定

MCP クライアントによって設定形式が異なります。
以下は `mcpServers` 形式に対応するクライアント向けの設定例です。

```json
{
  "mcpServers": {
    "ly-ads-mcp": {
      "type": "http",
      "url": "http://localhost:18765/mcp"
    }
  }
}
```

設定後、MCP クライアントからサーバーへ接続します。
ブラウザに表示される認可画面で、LINEヤフービジネス ID を使ってアクセスを許可してください。
設定項目や OAuth 認可の操作はクライアントごとに異なるため、利用する MCP クライアントのマニュアルを確認してください。

## 利用例

サーバーへの接続と OAuth による認可が完了したら、 MCP クライアントから次のように依頼できます。

```text
利用できるディスプレイ広告のアカウントを一覧で見せてください。
```

```text
アカウント ID 1234567890 の検索広告キャンペーンを取得してください。
```

```text
アカウント ID 1234567890 の検索広告で、キャンペーンに設定されている除外キーワードを確認してください。
```

多くのツールでは、ベースアカウント ID （ `baseAccountId` ）と広告アカウント ID （ `accountId` ）を使用します。
ID が分からない場合は、利用可能なベースアカウントと広告アカウントの取得を先に依頼してください。

## 生成済み API クライアント

`generated/` 配下に同梱している `ads_display_client` と `ads_search_client` は、OpenAPI Generator 7.13.0 で次のオプションを指定して生成しています。

```text
-g python
--additional-properties=packageName=<PACKAGE_NAME>,projectName=<PROJECT_NAME>,packageVersion=<PACKAGE_VERSION>
--global-property apiDocs=false,apiTests=false,modelDocs=false,modelTests=false
--skip-validate-spec
```

## 取り扱うデータと認証情報

LY Ads MCP Server から取得した LINEヤフー広告のデータは、MCP クライアントを介して AI エージェントへ提供されます。
信頼できる MCP クライアントでのみ使用し、各クライアントのデータ取り扱い条件を確認してください。

この MCP サーバーは `localhost` のみで接続を待ち受けます。
クライアントシークレット、アクセストークン、リフレッシュトークンをプロンプトへ入力しないでください。
