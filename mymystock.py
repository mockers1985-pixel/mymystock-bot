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

# 그룹 채팅방에 주가 정보를 보내는 함수
async def post_prices_to_group(context):
    logger.info(f"그룹 채팅방({GROUP_CHAT_ID})에 알림 발송을 시작합니다.")
    try:
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
                            code = matched_us_name.index[0]
                            market = '미국'
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

            except Exception as e:
                logger.error(f"'{term}' 처리 중 오류: {traceback.format_exc()}")
                message_content += f"⚠️ '{term}': 정보 조회 중 오류 발생\n"
            
            await asyncio.sleep(0.5)

        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message_content)
        logger.info(f"그룹 채팅방({GROUP_CHAT_ID})에 메시지 발송 성공")

    except Exception as e:
        logger.error(f"알림 생성 중 오류: {traceback.format_exc()}")
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"🚨 주가 정보 생성 중 오류가 발생했습니다.")


# ★★★★★ /now 명령어 함수 추가 ★★★★★
async def now(update, context):
    """/now 명령어 수신 시, 즉시 주가 정보를 조회하여 그룹 채팅방에 보냅니다."""
    # 그룹 채팅방에서만 동작하도록 제한 (선택 사항)
    if str(update.message.chat_id) != GROUP_CHAT_ID:
        await update.message.reply_text("이 명령어는 지정된 그룹 채팅방에서만 사용할 수 있습니다.")
        return
        
    await update.message.reply_text("알겠습니다! 지금 바로 주가 정보를 조회하여 그룹 채팅방에 올립니다...")
    # 예약된 작업과 동일한 함수를 즉시 실행
    await post_prices_to_group(context)


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    async def ping(update, context):
        await update.message.reply_text("저는 살아있습니다! 🤖 (v-final, /now 탑재)")
    
    # 명령어 핸들러 등록
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("now", now)) # /now 명령어 핸들러 등록
    
    job_queue = application.job_queue
    job_queue.run_repeating(post_prices_to_group, interval=840, first=10) # 14분 간격
    
    logger.info("그룹 채팅방 알림 봇이 시작되었습니다. (v-final, /now 탑재)")
    application.run_polling()

if __name__ == '__main__':
    main()
