import asyncio
import datetime as dt
import pytz
import logging
import pandas as pd
import FinanceDataReader as fdr
import traceback
from telegram import Bot
from telegram.ext import Application, CommandHandler, JobQueue
from flask import Flask # 웹서버 부품 Flask를 가져옵니다.
import threading # 두 가지 작업을 동시에 실행하기 위한 '스레딩' 도구를 가져옵니다.

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

# --- 웹서버 부분 (Render를 위한 가짜 가게) ---
app = Flask(__name__)

@app.route('/')
def hello_world():
    # Cron-Job.org 같은 서비스가 접속했을 때 보여줄 메시지
    return "저는 텔레그램 봇입니다. 계속 작동 중입니다!"

def run_flask():
    # Flask 웹서버를 0.0.0.0 주소와 Render가 지정해주는 포트(기본 10000)에서 실행
    app.run(host='0.0.0.0', port=10000)
# -----------------------------------------

# --- 텔레그램 봇 부분 (원래 우리의 공장) ---
async def generate_price_message():
    # (이 함수 내용은 이전과 동일하므로 생략)
    krx_list = fdr.StockListing('KRX')
    us_list = pd.concat([fdr.StockListing(market) for market in ['NASDAQ', 'NYSE', 'AMEX']])
    df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
    search_terms = df_list['종목명 또는 티커'].dropna().tolist()
    message_content = "🔔 주가 브리핑 (그룹)\n\n"
    start_date = dt.datetime.now() - dt.timedelta(days=10)
    for term in search_terms:
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

async def post_message_to_group(context):
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message)
    except Exception:
        logger.error(f"스케줄된 알림 발송 중 오류: {traceback.format_exc()}")

async def now_task(context):
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=context.job.chat_id, text=message)
    except Exception:
        logger.error(f"/now 작업 중 오류: {traceback.format_exc()}")
        await context.bot.send_message(chat_id=context.job.chat_id, text="죄송합니다, 정보를 가져오는 중 오류가 발생했습니다.")
        
async def now(update, context):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="알겠습니다! 지금 바로 주가 정보를 조회합니다. 잠시만 기다려주세요...")
    context.job_queue.run_once(now_task, 0, chat_id=chat_id, name=str(chat_id))

def main_bot():
    """텔레그램 봇을 실행하는 메인 함수"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    async def ping(update, context):
        await update.message.reply_text("저는 살아있습니다! 🤖 (Web Service)")
    
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("now", now))
    
    job_queue = application.job_queue
    job_queue.run_repeating(post_message_to_group, interval=840, first=10) # 14분 간격
    
    logger.info("텔레그램 봇이 시작되었습니다. (Web Service 모드)")
    # 이 함수는 무한히 실행됩니다.
    application.run_polling()
# -----------------------------------------

if __name__ == '__main__':
    # 1번 직원: 웹서버를 별도의 스레드에서 실행
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # 2번 직원: 텔레그램 봇을 메인 스레드에서 실행
    main_bot()
