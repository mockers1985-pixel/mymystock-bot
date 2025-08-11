import asyncio
import datetime as dt
import pytz
import logging
import pandas as pd
import FinanceDataReader as fdr
import traceback
from telegram import Bot
from telegram.ext import Application, CommandHandler, JobQueue
from flask import Flask
import threading

# --- 여기는 회원님의 정보로 수정하세요 ---
TELEGRAM_TOKEN = '8324065501:AAGH3Fw4rfb02Hdqlj5wRn0obfIsnctDrYY'
GROUP_CHAT_ID = '4896259196' 
# -----------------------------------

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 웹서버 부분 ---
app = Flask(__name__)
@app.route('/')
def hello_world():
    return "텔레그램 봇이 작동 중입니다!"
def run_flask():
    app.run(host='0.0.0.0', port=10000)

# --- 텔레그램 봇 부분 ---
async def generate_price_message():
    krx_list = fdr.StockListing('KRX')
    us_list = pd.concat([fdr.StockListing(market) for market in ['NASDAQ', 'NYSE', 'AMEX']])
    df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
    search_terms = df_list['종목명 또는 티커'].dropna().tolist()
    
    message_content = "🔔 <b>주가 브리핑 (그룹)</b>\n\n"
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

            # ★★★★★ 하이퍼링크 생성 로직 ★★★★★
            if market == '국내':
                stock_url = f"https://finance.naver.com/item/main.naver?code={code}"
            else: # 미국 주식
                stock_url = f"https://finance.yahoo.com/quote/{code}"

            # 아이콘 및 서식 설정
            icon_change = '🔴' if change > 0 else '🔵' if change < 0 else '⚪'
            sign = '+' if change > 0 else ''
            icon_market = '📈' if market == '국내' else '🇺🇸'
            currency = '원' if market == '국내' else '$'
            price_format = '{:,.0f}' if market == '국내' else '{:,.2f}'
            change_format = '{:,.0f}' if market == '국내' else '{:,.2f}'

            # ★★★★★ 메시지에 하이퍼링크 적용 ★★★★★
            message_content += (f'{icon_market} <b><a href="{stock_url}">{name_to_display}</a></b>\n'
                                f"<code>{price_format.format(latest_price)} {currency}</code> "
                                f"{icon_change} <code>{sign}{change_format.format(change)} ({sign}{change_percent:.2f}%)</code>\n\n")

        except Exception:
            message_content += f"⚠️ '<b>{term}</b>': 정보 조회 중 오류가 발생했습니다.\n\n"
        
        await asyncio.sleep(0.1)
    
    return message_content

# 메시지를 보내는 모든 함수에 parse_mode='HTML' 추가
async def post_message_to_group(context):
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message, parse_mode='HTML')
    except Exception:
        logger.error(f"스케줄 알림 오류: {traceback.format_exc()}")

async def now_task(context):
    try:
        message = await generate_price_message()
        await context.bot.send_message(chat_id=context.job.chat_id, text=message, parse_mode='HTML')
    except Exception:
        await context.bot.send_message(chat_id=context.job.chat_id, text="죄송합니다, 오류가 발생했습니다.", parse_mode='HTML')
        
async def now(update, context):
    await update.message.reply_text("알겠습니다! 지금 바로 주가 정보를 조회합니다...")
    context.job_queue.run_once(now_task, 0, chat_id=update.effective_chat.id, name=str(update.effective_chat.id))

def main_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    async def ping(update, context):
        await update.message.reply_text("저는 살아있습니다! 🤖 (링크 기능 탑재)")
    
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("now", now))
    
    job_queue = application.job_queue
    job_queue.run_repeating(post_message_to_group, interval=840, first=10)
    
    logger.info("텔레그램 봇이 시작되었습니다. (Web Service, 최종 링크 버전)")
    application.run_polling()

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    main_bot()
