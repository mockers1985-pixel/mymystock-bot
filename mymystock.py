from flask import Flask, render_template, jsonify
import pandas as pd
import FinanceDataReader as fdr
import datetime as dt
import logging
import gspread # 구글 시트 라이브러리
from oauth2client.service_account import ServiceAccountCredentials # 구글 인증 라이브러리
import os # 환경 변수 및 파일 경로를 다루기 위한 라이브러리

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask 앱 생성
app = Flask(__name__)

# --- 구글 시트 설정 ---
# Render의 Secret File 경로 설정
# Render는 비밀 파일을 '/etc/secrets/' 경로에 저장합니다.
SECRET_KEY_FILE_PATH = '/etc/secrets/river-city-468802-r8-9c7520b76a38.json' # ★★★ .json 파일의 실제 이름으로 바꿔주세요 ★★★
# 구글 시트 API 범위 설정
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

def get_stock_data_from_gsheet():
    """구글 시트에서 주식 목록을 읽고, 주가 정보를 조회하여 문자열로 반환하는 함수"""
    logger.info("구글 시트에서 데이터 조회를 시작합니다.")
    try:
        # 1. 구글 시트 인증
        creds = ServiceAccountCredentials.from_json_keyfile_name(SECRET_KEY_FILE_PATH, SCOPES)
        client = gspread.authorize(creds)
        
        # 2. 구글 시트 파일 열기 (★★★★★ 파일 이름을 본인의 것으로 바꿔주세요 ★★★★★)
        sheet = client.open("my stock list").sheet1
        
        # 3. 시트에서 데이터 읽어오기
        records = sheet.get_all_records()
        df_list = pd.DataFrame(records)
        
        # '종목명 또는 티커' 컬럼이 없는 경우 오류 처리
        if '종목명 또는 티커' not in df_list.columns:
            return "오류: 구글 시트에 '종목명 또는 티커' 컬럼이 없습니다."
            
        search_terms = df_list['종목명 또는 티커'].dropna().tolist()

        # (이하 주가 정보를 조회하고 메시지를 만드는 로직은 이전과 동일)
        krx_list = fdr.StockListing('KRX')
        us_list = pd.concat([fdr.StockListing(market) for market in ['NASDAQ', 'NYSE', 'AMEX']])
        message_content = ""
        start_date = dt.datetime.now() - dt.timedelta(days=10)
        
        for term in search_terms:
            # ... (이전과 동일한 종목 검색, 가격 조회, 메시지 생성 로직) ...
            # 코드가 길어지므로 생략합니다. 이전 버전의 코드를 그대로 사용합니다.
            code, name_to_display, market = None, term, None
            try:
                matched_krx = krx_list[krx_list['Name'] == term]
                if not matched_krx.empty:
                    code, market = matched_krx['Code'].iloc[0], '국내'
                else:
                    if term.upper() in us_list.index:
                        code, market = term.upper(), '미국'
                        name_to_display = us_list.loc[code, 'Name']
                    else:
                        matched_us_name = us_list[us_list['Name'].str.contains(term, case=False, na=False)]
                        if not matched_us_name.empty:
                            code = matched_us_name.index[0]
                            market = '미국'
                            name_to_display = matched_us_name['Name'].iloc[0]
                
                if not code:
                    message_content += f"❓ '{term}' 종목/티커를 찾을 수 없습니다.\n"
                    continue
                
                df_price = fdr.DataReader(code, start=start_date)
                if len(df_price) < 2:
                    message_content += f"📉 {name_to_display}: 데이터 부족\n"
                    continue

                latest_price = df_price['Close'].iloc[-1]
                previous_price = df_price['Close'].iloc[-2]
                change = latest_price - previous_price
                change_percent = (change / previous_price) * 100 if previous_price != 0 else 0

                if change > 0: icon_change = '🔴'
                elif change < 0: icon_change = '🔵'
                else: icon_change = '⚪'
                sign = '+' if change > 0 else ''
                currency = '원' if market == '국내' else '$'
                price_format = '{:,.0f}' if market == '국내' else '{:,.2f}'
                change_format = '{:,.0f}' if market == '국내' else '{:,.2f}'

                message_content += (f"{name_to_display}:\n"
                                    f"  현재가: {price_format.format(latest_price)} {currency}\n"
                                    f"  등락: {icon_change} {sign}{change_format.format(change)} ({sign}{change_percent:.2f}%)\n\n")

            except Exception as e:
                logger.error(f"'{term}' 처리 중 오류: {e}")
                message_content += f"⚠️ '{term}': 정보 조회 중 오류가 발생했습니다.\n\n"
        
        logger.info("구글 시트 데이터 조회를 완료했습니다.")
        return message_content

    except Exception as e:
        logger.error(f"구글 시트 처리 중 심각한 오류 발생: {e}")
        return f"오류가 발생했습니다: {e}"

# --- 웹페이지 라우팅 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-stock-data')
def get_stock_data_api():
    data = get_stock_data_from_gsheet() # 엑셀 대신 구글 시트 함수 호출
    return jsonify(message=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)


