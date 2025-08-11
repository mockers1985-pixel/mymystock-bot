import asyncio
import datetime as dt
import pytz
import logging
import pandas as pd
import FinanceDataReader as fdr
import traceback
from telegram import Bot
from telegram.ext import Application, CommandHandler, JobQueue

# --- 여기를 수정하세요 ---
TELEGRAM_TOKEN = '8324065501:AAGH3Fw4rfb02Hdqlj5wRn0obfIsnctDrYY'
# 2단계에서 알아낸 그룹 채팅방의 ID를 입력하세요. (마이너스 부호 포함, 따옴표 안에)
GROUP_CHAT_ID = '-4896259196' 
# ---------------------

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 그룹 채팅방에 주가 정보를 보내는 함수
async def post_prices_to_group(context):
    logger.info(f"그룹 채팅방({GROUP_CHAT_ID})에 알림 발송을 시작합니다.")

    # 주가 정보 가져오는 로직 (이전과 동일)
    try:
        krx_list = fdr.StockListing('KRX')
        us_list = pd.concat([fdr.StockListing(market) for market in ['NASDAQ', 'NYSE', 'AMEX']])
        
        df_list = pd.read_excel("stock_list.xlsx", dtype={'종목명 또는 티커': str})
        search_terms = df_list['종목명 또는 티커'].dropna().tolist()
        
        message_content = "🔔 1시간 주가 브리핑 (그룹)\n\n"
        start_date = dt.datetime.now() - dt.timedelta(days=10)
        
        for term in search_terms:
            code, name_to_display, market = None, term, None
            matched_krx = krx_list[krx_list['Name'] == term]
            if not matched_krx.empty:
                code, market = matched_krx['Code'].iloc[0], '국내'
            elif term in us_list.index:
                code, market = term, '미국'
                name_to_display = us_list.loc[term, 'Name']
            else:
                matched_us_name = us_list[us_list['Name'] == term]
                if not matched_us_name.empty:
                    code, market = matched_us_name.index[0], '미국'
            
            if not code:
                message_content += f"❓ '{term}' 종목/티커를 찾을 수 없습니다.\n"
                continue
            
            df_price = fdr.DataReader(code, start=start_date)
            latest_price = df_price['Close'].iloc[-1]
            currency = '원' if market == '국내' else '$'
            icon = '📈' if market == '국내' else '🇺🇸'
            price_format = '{:,.0f}' if market == '국내' else '{:,.2f}'
            message_content += f"{icon} {name_to_display}: {price_format.format(latest_price)} {currency}\n"
            await asyncio.sleep(0.2)

        # 지정된 그룹 채팅방으로 메시지 발송
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message_content)
        logger.info(f"그룹 채팅방({GROUP_CHAT_ID})에 메시지 발송 성공")

    except Exception as e:
        logger.error(f"그룹 채팅방 알림 생성 중 오류 발생: {e}")
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"🚨 주가 정보 생성 중 오류가 발생했습니다: {e}")


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 이제 /start, /stop 명령어는 필요 없습니다.
    # 원한다면, 봇이 살아있는지 확인하는 /ping 같은 간단한 명령어를 추가할 수 있습니다.
    async def ping(update, context):
        await update.message.reply_text("저는 살아있습니다! 🤖")
    
    application.add_handler(CommandHandler("ping", ping))
    
    job_queue = application.job_queue
    job_queue.run_repeating(post_prices_to_group, interval=3600, first=10)
    
    logger.info("그룹 채팅방 알림 봇이 시작되었습니다.")
    
    application.run_polling()

if __name__ == '__main__':
    main()
