from flask import Flask, render_template, jsonify
import pandas as pd
import FinanceDataReader as fdr
import datetime as dt
import logging

# --- 전역 변수 설정 ---
# 이 변수들은 서버가 켜질 때 딱 한 번만 채워집니다.
KRX_LIST = None
US_LIST = None

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask 앱 생성
app = Flask(__name__)

def preload_stock_lists():
    """서버 시작 시, 주식 목록 전체를 미리 불러와 전역 변수에 저장합니다."""
    global KRX_LIST, US_LIST
    logger.info("주식 목록을 미리 불러옵니다... (서버 시작 작업)")
    try:
        KRX_LIST = fdr.StockListing('KRX')
        nasdaq = fdr.StockListing('NASDAQ')
        nyse = fdr.StockListing('NYSE')
        amex = fdr.StockListing('AMEX')
        US_LIST = pd.concat([nasdaq, nyse, amex])
        logger.info("주식 목록 미리 불러오기 완료.")
    except Exception as e:
        logger.error(f"주식 목록을 미리 불러오는 중 오류 발생: {e}")
        # 실패 시, 비어있는 데이터프레임으로 초기화하여 다른 기능의 오류를 방지
        KRX_LIST = pd.DataFrame()
        US_LIST = pd.DataFrame()

def get_stock_data_from_gsheet():
    """구글 시트에서 주식 목록을 읽고, 미리 불러온 목록을 사용해 빠르게 조회합니다."""
    logger.info("구글 시트에서 데이터 조회를 시작합니다.")
    try:
        # 엑셀 파일을 읽는 것으로 대체 (구글 시트 인증 부분은 동일하게 작동한다고 가정)
        df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
        search_terms = df_list['종목명 또는 티커'].dropna().tolist()
        
        message_content = ""
        start_date = dt.datetime.now() - dt.timedelta(days=10)
        
        # 주식 목록을 매번 새로 불러오는 대신, 미리 로드된 전역 변수를 사용합니다.
        for term in search_terms:
            code, name_to_display, market = None, term, None
            try:
                # (이전과 동일한 종목 검색 및 가격 조회 로직)
                # 단, krx_list와 us_list 대신 KRX_LIST와 US_LIST를 사용
                matched_krx = KRX_LIST[KRX_LIST['Name'] == term]
                if not matched_krx.empty:
                    code, market = matched_krx['Code'].iloc[0], '국내'
                else:
                    if term.upper() in US_LIST.index:
                        code, market = term.upper(), '미국'
                        name_to_display = US_LIST.loc[code, 'Name']
                    else:
                        matched_us_name = US_LIST[US_LIST['Name'].str.contains(term, case=False, na=False)]
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

                # (이하 메시지 생성 로직은 동일)
                latest_price, previous_price = df_price['Close'].iloc[-2:].tolist()
                change = latest_price - previous_price
                change_percent = (change / previous_price) * 100 if previous_price != 0 else 0
                icon_change = '🔴' if change > 0 else '🔵' if change < 0 else '⚪'
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
        
        return message_content

    except Exception as e:
        logger.error(f"데이터 조회 중 심각한 오류 발생: {e}")
        return f"오류가 발생했습니다: {e}"

# --- 웹페이지 라우팅 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-stock-data')
def get_stock_data_api():
    data = get_stock_data_from_gsheet()
    return jsonify(message=data)

if __name__ == '__main__':
    # 서버가 시작될 때, 주식 목록을 딱 한 번만 미리 불러옵니다.
    preload_stock_lists()
    # 개발용 서버 실행
    app.run(host='0.0.0.0', port=10000, debug=False) # 운영 환경에서는 Debug 모드를 끄는 것이 좋습니다.
