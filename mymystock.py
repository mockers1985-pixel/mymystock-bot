import asyncio
import datetime as dt
import pytz
import logging
import pandas as pd
import FinanceDataReader as fdr
import traceback
from telegram import Bot
from telegram.ext import Application, CommandHandler, JobQueue

# --- 여기는 회원님의 정보로 수정하세요 ---
TELEGRAM_TOKEN = '8324065501:AAGH3Fw4rfb02Hdqlj5wRn0obfIsnctDrYY'
CHAT_ID = '55386148'
# -----------------------------------

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 이름(KR/US)과 티커(US)로 주가를 가져오는 최종 완성 함수
async def fetch_and_send_prices_by_name(context):
    """엑셀에서 종목명 또는 티커를 읽어 현재가와 등락률을 알려줍니다."""
    try:
        logger.info("주식 목록을 불러오는 중... (KRX, NASDAQ, NYSE, AMEX)")
        krx_list = fdr.StockListing('KRX')
        
        # 미국 시장을 각각 불러와서 하나로 합칩니다.
        nasdaq_list = fdr.StockListing('NASDAQ')
        nyse_list = fdr.StockListing('NYSE')
        amex_list = fdr.StockListing('AMEX')
        us_list = pd.concat([nasdaq_list, nyse_list, amex_list])
        
        logger.info("주식 목록 로딩 완료.")

        # 엑셀 파일의 첫 번째 시트, '종목명 또는 티커' 열을 문자열로 읽어옵니다.
        df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
        # 비어있는 행은 무시하고, 실제 내용이 있는 항목만 리스트로 만듭니다.
        search_terms = df_list['종목명 또는 티커'].dropna().tolist()
        
        message = "🔔 매시간 주가 브리핑 (글로벌)\n\n"
        # 주가 조회를 위해 오늘로부터 10일 전 날짜를 계산합니다.
        start_date = dt.datetime.now() - dt.timedelta(days=10)
        
        for term in search_terms:
            code = None
            market = None
            name_to_display = term

            try:
                # 1. 한국 주식 '이름'으로 검색합니다.
                matched_krx = krx_list[krx_list['Name'] == term]
                if not matched_krx.empty:
                    code = matched_krx['Code'].iloc[0]
                    market = '국내'
                else:
                    # 2. 없으면 미국 주식 '티커'로 검색합니다. (대소문자 구분 없음)
                    if term.upper() in us_list.index:
                        code = term.upper()
                        market = '미국'
                        name_to_display = us_list.loc[code, 'Name']
                    else:
                        # 3. 그래도 없으면, 미국 주식 '이름'에 단어가 "포함"된 것을 검색합니다.
                        matched_us_name = us_list[us_list['Name'].str.contains(term, case=False, na=False)]
                        if not matched_us_name.empty:
                            code = matched_us_name['Symbol'].iloc[0]
                            market = '미국'
                            name_to_display = matched_us_name['Name'].iloc[0]
                
                # 4. 모든 방법으로 찾지 못한 경우
                if code is None:
                    message += f"❓ '{term}' 종목/티커를 찾을 수 없습니다.\n\n"
                    continue
                
                # 5. 찾은 코드로 데이터를 요청합니다.
                df_price = fdr.DataReader(str(code), start=start_date)
                
                if df_price.empty or 'Close' not in df_price.columns:
                    message += f"📉 {name_to_display}: 현재가 정보 없음\n\n"
                    continue 

                # 6. 등락률 계산을 위한 가격 정보 추출
                latest_price = df_price['Close'].iloc[-1]
                base_price = df_price['Close'].iloc[-2] if len(df_price) > 1 else df_price['Open'].iloc[-1]

                change = latest_price - base_price
                change_percent = (change / base_price) * 100
                
                # 7. 등락 표시 문자열 생성
                if change > 0:
                    change_str = f"🔺 {change:,.2f} ({change_percent:+.2f}%)"
                elif change < 0:
                    change_str = f"🔻 {change:,.2f} ({change_percent:+.2f}%)"
                else:
                    change_str = f"▬ 0 (0.00%)"

                # 통화 및 아이콘 설정
                currency = '원' if market == '국내' else '$'
                icon = '📈' if market == '국내' else '🇺🇸'
                
                # 8. 최종 메시지 조합
                if pd.isna(latest_price):
                    message += f"📉 {name_to_display}: 현재가 정보 없음 (NaN)\n\n"
                else:
                    price_format = '{:,.0f}' if market == '국내' else '{:,.2f}'
                    message += f"{icon} {name_to_display}: {price_format.format(latest_price)} {currency}\n"
                    message += f"    {change_str}\n\n"

            except Exception as e:
                detailed_error_report = traceback.format_exc()
                logger.error(f"'{term}' 처리 중 오류 발생: {e}\n--- 상세 보고서 ---\n{detailed_error_report}")
                message += f"⚠️ '{term}': 정보 조회 중 오류 발생\n\n"
            
            await asyncio.sleep(0.5) # 텔레그램 메시지 제한을 피하기 위한 지연

        await context.bot.send_message(chat_id=CHAT_ID, text=message)
        logger.info("성공적으로 (글로벌 기준) 여러 종목의 주가 정보를 보냈습니다.")

    except Exception as e:
        logger.error(f"주가 정보 전송 중 오류 발생: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text=f"주가 정보를 가져오는 데 실패했습니다: {e}")


# '/start'와 '/now' 명령어
async def start(update, context):
    user = update.effective_user
    await update.message.reply_html(
        rf"안녕하세요, {user.mention_html()}님! 엑셀의 '종목명' 또는 '티커' 기준으로 주가와 등락률을 알려드립니다."
    )
    await fetch_and_send_prices_by_name(context)

async def now(update, context):
    await update.message.reply_text("엑셀 파일의 모든 종목 주가를 지금 바로 조회합니다...")
    await fetch_and_send_prices_by_name(context)

# 메인 실행 부분
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("now", now))

    job_queue = application.job_queue
    
    # ★★★★★ 여기가 "매시간 정각" 설정입니다! ★★★★★
    # 한국 시간대(KST) 설정
    kst = pytz.timezone('Asia/Seoul')
    # 매시간 0분 0초에 fetch_and_send_prices_by_name 함수 실행 예약
    job_queue.run_custom(fetch_and_send_prices_by_name, job_kwargs={'trigger': 'cron', 'minute': 0, 'second': 5, 'timezone': kst})
    
    logger.info("봇이 시작되었습니다. (매시간 정각 기준) 알림을 보냅니다.")
    
    application.run_polling()

if __name__ == '__main__':
    main()