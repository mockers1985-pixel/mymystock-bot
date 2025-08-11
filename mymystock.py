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
GROUP_CHAT_ID = '4896259196' 
# -----------------------------------

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 주가 정보를 생성하는 핵심 로직 함수
async def generate_price_message():
    """주가 정보를 조회하여 메시지 문자열을 생성하고 반환합니다."""
    krx_list = fdr.StockListing('KRX')
    us_list = pd.concat([fdr.StockListing(market) for market in ['NASDAQ', 'NYSE', 'AMEX']])
    df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
    search_terms = df_list['종목명 또는 티커'].dropna().tolist()
    
    message_content = "🔔 주가 브리핑 (그룹)\n\n"
    start_date = dt.datetime.now() - dt.timedelta(days=10)
    
    for term in search_terms:
        # (이전과 동일한 종목 검색 및 가격 조회 로직)
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
                        code, market = matched_us_name.index[0], '미국'
                        name_to_display = matched_us_name['Name'].iloc[0]
            
            if not code:
                message_content += f"❓ '{term}' 종목/티커를 찾을 수 없습니다.\n"
                continue
            
            df_price = fdr.DataReader(code, start=start_date)
            if len(df_price) < 2:
                message_content += f"📉 {name_to_display}: 등락 비교 데이터 부족\n"
                continue

            latest_price = df_price['Close'].iloc[-1]
            previous_price = df_price['Close'].iloc[-2]
            change = latest_price - previous_price
            change_icon = '▲' if change > 0 else '▼' if change < 0 else '-'
            currency = '원' if market == '국내' else '$'
            icon = '📈' if market == '국내' else '🇺🇸'
            price_format = '{:,.0f}' if market == '국내' else '{:,.2f}'
            change_format = '{:+.0f}' if market == '국내' else '{:+.2f}'
            
            message_content += (f"{icon} {name_to_display}: {price_format.format(latest_price)} {currency} "
                                f"({change_icon} {change_format.format(change)})\n")

        except Exception:
            message_content += f"⚠️ '{term}': 정보 조회 중 오류 발생\n"
        
        await asyncio.sleep(0.1)
    
    return message_content

# 생성된 메시지를 그룹 채팅방에 보내는 함수
async def post_message_to_group(context):
    logger.info("스케줄된 알림 발송을 시작합니다.")
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message)
        logger.info("스케줄된 알림 발송 성공.")
    except Exception as e:
        logger.error(f"스케줄된 알림 발송 중 오류: {traceback.format_exc()}")

# ★★★★★ /now 명령어 로직 개선 ★★★★★
async def now(update, context):
    """/now 명령어 수신 시, 별도의 작업을 즉시 실행하여 결과를 보냅니다."""
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="알겠습니다! 지금 바로 주가 정보를 조회합니다. 잠시만 기다려주세요...")
    
    # 즉시 실행할 작업을 JobQueue에 추가합니다.
    context.job_queue.run_once(now_task, 0, chat_id=chat_id, name=str(chat_id))

async def now_task(context):
    """/now 명령에 의해 실제로 실행되는 작업 함수"""
    job = context.job
    logger.info(f"/now 요청({job.chat_id})에 대한 작업 실행.")
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=job.chat_id, text=message)
        logger.info(f"/now 요청({job.chat_id})에 대한 작업 성공.")
    except Exception as e:
        logger.error(f"/now 작업 중 오류: {traceback.format_exc()}")
        await context.bot.send_message(chat_id=job.chat_id, text="죄송합니다, 정보를 가져오는 중 오류가 발생했습니다.")


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    async def ping(update, context):
        await update.message.reply_text("저는 살아있습니다! 🤖 (v-final, /now 개선)")
    
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("now", now))
    
    job_queue = application.job_queue
    # 주기적인 스케줄링 작업
    job_queue.run_repeating(post_message_to_group, interval=840, first=10)
    
    logger.info("그룹 채팅방 알림 봇이 시작되었습니다. (v-final, /now 개선)")
    application.run_polling()

if __name__ == '__main__':
    main()
