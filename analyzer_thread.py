import asyncio
import matplotlib
matplotlib .use ('Agg')
import matplotlib .pyplot as plt
import pandas as pd
from datetime import datetime
from wordcloud import WordCloud
from PyQt5 .QtCore import QThread ,pyqtSignal ,QMetaObject ,Qt ,Q_ARG
from telethon import TelegramClient
from telethon .tl .functions .messages import GetDiscussionMessageRequest
from telethon .tl .functions .channels import GetFullChannelRequest
from telethon .errors import RPCError ,SessionPasswordNeededError ,PhoneCodeInvalidError ,ApiIdInvalidError ,AuthKeyUnregisteredError
from analysis_helpers import normalize_text
from config import russian_stopwords
class AnalyzerThread (QThread ):
    progress_signal =pyqtSignal (str )
    result_signal =pyqtSignal (dict )
    error_signal =pyqtSignal (str )
    def __init__ (self ,api_id ,api_hash ,username ,start_date ,end_date ,limit_messages ,limit_comments_per_post ,
    parent_window ):
        super ().__init__ ()
        self .api_id =int (api_id )if api_id else None
        self .api_hash =api_hash
        self .username =username
        self .start_date =start_date
        self .end_date =end_date
        self .limit_messages =limit_messages
        self .limit_comments_per_post =limit_comments_per_post
        self ._input_value =None
        self ._input_event =asyncio .Event ()
        self .parent_window =parent_window
        self .parent_window .user_input_signal .connect (self .on_user_input_received )
    def request_input_from_main_thread (self ,title ,label ):
        self ._input_value =None
        self ._input_event .clear ()
        QMetaObject .invokeMethod (self .parent_window ,"prompt_user_input",Qt .QueuedConnection ,
        Q_ARG (str ,title ),Q_ARG (str ,label ))
    def on_user_input_received (self ,value ):
        self ._input_value =value
        self ._input_event .set ()
    async def async_request_input (self ,title ,label ):
        loop =asyncio .get_event_loop ()
        await loop .run_in_executor (None ,self .request_input_from_main_thread ,title ,label )
        await self ._input_event .wait ()
        return self ._input_value
    async def get_phone_callback (self ):
        return await self .async_request_input ("Требуется номер телефона",
        "Введите ваш номер телефона (в международном формате, например +1234567890):")
    async def get_code_callback (self ):
        return await self .async_request_input ("Требуется код подтверждения","Введите код, полученный в Telegram:")
    async def get_password_callback (self ,hint =''):
        prompt =f"Требуется пароль двухфакторной аутентификации"
        if hint :
            prompt +=f" (подсказка: {hint })"
        prompt +=":"
        return await self .async_request_input ("Требуется пароль",prompt )
    def run (self ):
        try :
            if not self .api_id or not self .api_hash :
                self .error_signal .emit ("API ID и API Hash должны быть указаны.")
                return
            asyncio .run (self .fetch_data ())
        except ApiIdInvalidError :
            self .error_signal .emit ("Неверный API ID. Пожалуйста, проверьте его.")
        except AuthKeyUnregisteredError :
            self .error_signal .emit (
            "Ключ авторизации не зарегистрирован или API Hash неверен. Убедитесь, что API ID и Hash корректны и активны, или пересоздайте сессию.")
        except RPCError as e :
            self .error_signal .emit (f"Ошибка RPC Telegram: {e }. Возможно, проблемы с сетью или API Telegram.")
        except PhoneCodeInvalidError :
            self .error_signal .emit ("Введен неверный код подтверждения.")
        except SessionPasswordNeededError :
            self .error_signal .emit (
            "Требуется пароль двухфакторной аутентификации, но он не был предоставлен или не верен.")
        except ConnectionError :
            self .error_signal .emit ("Ошибка подключения. Проверьте ваше интернет-соединение.")
        except ValueError as e :
            if "Невозможно найти ни одну сущность, соответствующую"in str (e ):
                self .error_signal .emit (
                f"Не удалось найти канал '{self .username }'. Проверьте правильность имени пользователя.")
            else :
                self .error_signal .emit (f"Ошибка значения: {str (e )}")
        except Exception as e :
            self .error_signal .emit (f"Непредвиденная ошибка: {type (e ).__name__ }: {str (e )}")
    async def fetch_data (self ):
        self .progress_signal .emit ("🔌 Подключение к Telegram...")
        async with TelegramClient (f'telegram_analyzer_session_{self .username }',self .api_id ,self .api_hash ,
        device_model ="Приложение Telegram Анализатор",system_version ="1.0")as client :
            await client .connect ()
            if not await client .is_user_authorized ():
                self .progress_signal .emit ("🔐 Требуется авторизация...")
                phone =await self .get_phone_callback ()
                if not phone :
                    self .error_signal .emit ("Авторизация отменена: номер телефона не введен.")
                    return
                try :
                    await client .send_code_request (phone )
                except RPCError as e :
                    self .error_signal .emit (f"Ошибка при запросе кода: {e }")
                    return
                code =await self .get_code_callback ()
                if not code :
                    self .error_signal .emit ("Авторизация отменена: код не введен.")
                    return
                try :
                    await client .sign_in (phone =phone ,code =code )
                except SessionPasswordNeededError :
                    password =await self .get_password_callback ()
                    if not password :
                        self .error_signal .emit ("Авторизация отменена: пароль 2FA не введен.")
                        return
                    await client .sign_in (password =password )
                except PhoneCodeInvalidError :
                    self .error_signal .emit ("Неверный код подтверждения.")
                    return
                except RPCError as e :
                    self .error_signal .emit (f"Ошибка входа: {e }")
                    return
            self .progress_signal .emit ("📨 Получение данных о канале...")
            channel =await client .get_entity (self .username )
            full_channel =await client (GetFullChannelRequest (channel =channel ))
            participants =full_channel .full_chat .participants_count or 0
            self .progress_signal .emit (f"👥 Количество подписчиков: {participants }")
            self .progress_signal .emit ("📨 Сбор сообщений канала...")
            messages_data =[]
            async for message in client .iter_messages (channel ,limit =self .limit_messages ,
            offset_date =pd .to_datetime (self .end_date ,
            errors ='coerce')if self .end_date else None ,
            reverse =True if self .start_date else False ):
                if self .start_date and message .date .timestamp ()<pd .to_datetime (self .start_date ,
                errors ='coerce').timestamp ():
                    if not (self .start_date and self .end_date ):
                        break
                if self .end_date and message .date .timestamp ()>pd .to_datetime (self .end_date ,
                errors ='coerce').timestamp ():
                    continue
                if message .message :
                    total_reactions =0
                    if message .reactions and message .reactions .results :
                        for r in message .reactions .results :
                            total_reactions +=r .count
                    total_comments =0
                    if message .replies and message .replies .replies :
                        total_comments =message .replies .replies
                    messages_data .append ({
                    'id':message .id ,
                    'message':message .message ,
                    'views':message .views or 0 ,
                    'date':message .date ,
                    'reactions':total_reactions ,
                    'comments_count':total_comments
                    })
            if not messages_data :
                self .error_signal .emit ("Не удалось получить сообщения или канал пуст в указанном диапазоне.")
                return
            df =pd .DataFrame (messages_data )
            df ['date']=pd .to_datetime (df ['date']).dt .tz_convert (None )
            if self .start_date :
                start_dt =pd .to_datetime (self .start_date ,errors ='coerce')
                if pd .notna (start_dt ):
                    df =df [df ['date']>=start_dt ]
            if self .end_date :
                end_dt =pd .to_datetime (self .end_date ,errors ='coerce')
                if pd .notna (end_dt ):
                    df =df [df ['date']<=end_dt .replace (hour =23 ,minute =59 ,second =59 )]
            if df .empty :
                self .error_signal .emit ("Нет сообщений в выбранном диапазоне дат после фильтрации.")
                return
            avg_views =df ['views'].mean ()if not df .empty else 0
            safe_participants =participants if participants >0 else 1
            engagement_rate =(avg_views /safe_participants )*100 if safe_participants >0 else 0
            average_reactions =df ['reactions'].mean ()if not df ['reactions'].empty else 0
            average_comments_from_posts =df ['comments_count'].mean ()if not df ['comments_count'].empty else 0
            wordcloud_path ,activity_plot_path ,recommendations =self .generate_insights (df ,engagement_rate ,
            participants )
            hourly_plot_path =self .generate_hourly_insights (df )
            comments_df =pd .DataFrame ()
            linked_chat_id =full_channel .full_chat .linked_chat_id
            if linked_chat_id and linked_chat_id !=0 and self .limit_comments_per_post >0 :
                self .progress_signal .emit (f"💬 Сбор комментариев из связанного чата (ID: {linked_chat_id })...")
                comments_df =await self .fetch_comments_for_posts (client ,df ,channel ,linked_chat_id )
            elif self .limit_comments_per_post ==0 :
                self .progress_signal .emit ("ℹ️ Сбор комментариев отключен (лимит 0).")
            else :
                self .progress_signal .emit ("ℹ️ Связанный чат для комментариев не найден или не указан.")
            result ={
            "participants":participants ,
            "average_views":avg_views ,
            "engagement_rate":engagement_rate ,
            "average_reactions":average_reactions ,
            "average_comments_from_posts":average_comments_from_posts ,
            "wordcloud_path":wordcloud_path ,
            "activity_plot_path":activity_plot_path ,
            "hourly_plot_path":hourly_plot_path ,
            "recommendations":recommendations ,
            "df":df ,
            "comments_df":comments_df
            }
            self .result_signal .emit (result )
    async def fetch_comments_for_posts (self ,client ,df_posts ,channel_entity ,linked_chat_id ):
        comments_data =[]
        total_posts =len (df_posts )
        for i ,(_ ,row )in enumerate (df_posts .iterrows ()):
            channel_msg_id =row ['id']
            self .progress_signal .emit (
            f"💬 Обработка комментариев для поста {i +1 }/{total_posts } (ID: {channel_msg_id })")
            discussion_msg_entity =None
            try :
                discussion_msg_entity =await client (GetDiscussionMessageRequest (
                peer =channel_entity ,
                msg_id =channel_msg_id
                ))
            except RPCError as e :
                self .progress_signal .emit (
                f"⚠️ Не удалось получить точку обсуждения для поста {channel_msg_id }: {type (e ).__name__ }")
                continue
            if discussion_msg_entity and discussion_msg_entity .messages :
                discussion_msg_anchor =discussion_msg_entity .messages [0 ]
                try :
                    async for comment_msg in client .iter_messages (linked_chat_id ,limit =self .limit_comments_per_post ,
                    reply_to =discussion_msg_anchor .id ):
                        if comment_msg .message :
                            comments_data .append ({
                            'comment':comment_msg .message ,
                            'date':comment_msg .date ,
                            'post_id':channel_msg_id
                            })
                except RPCError as e :
                    self .progress_signal .emit (
                    f"⚠️ Ошибка при сборе комментариев для поста {channel_msg_id } в чате {linked_chat_id }: {type (e ).__name__ }")
                except Exception as e :
                    self .progress_signal .emit (
                    f"⚠️ Неизвестная ошибка при сборе комментариев для поста {channel_msg_id }: {type (e ).__name__ }")
            await asyncio .sleep (0.1 )
        comments_df =pd .DataFrame (comments_data )
        if not comments_df .empty :
            comments_df ['date']=pd .to_datetime (comments_df ['date']).dt .tz_convert (None )
        return comments_df
    def generate_insights (self ,df ,engagement_rate ,participants ):
        words =' '.join (df ['message'].dropna ()).split ()
        filtered_words =[word for word in normalize_text (' '.join (words ))if
        word .lower ()not in russian_stopwords and len (word )>2 ]
        wordcloud_path ="wordcloud.png"
        if filtered_words :
            wordcloud =WordCloud (width =1600 ,height =800 ,background_color ='white',colormap ='viridis').generate (
            ' '.join (filtered_words ))
            wordcloud .to_file (wordcloud_path )
        else :
            fig ,ax =plt .subplots (figsize =(16 ,8 ))
            ax .text (0.5 ,0.5 ,"Нет слов для облака",ha ='center',va ='center',fontsize =20 )
            ax .axis ('off')
            plt .savefig (wordcloud_path ,facecolor ='white')
            plt .close (fig )
        daily_activity =df .resample ('D',on ='date').size ()
        activity_plot_path ="activity_plot.png"
        plt .figure (figsize =(16 ,8 ))
        if daily_activity .empty :
            plt .text (0.5 ,0.5 ,"Нет данных для отображения активности",ha ='center',va ='center',fontsize =16 )
            plt .axis ('off')
        else :
            plt .plot (daily_activity .index ,daily_activity .values ,marker ='o',color ='purple',linestyle ='--')
            plt .title ('Активность по датам',fontsize =16 ,color ='darkblue')
            plt .xlabel ('Дата',fontsize =14 )
            plt .ylabel ('Постов в канале',fontsize =14 )
            plt .grid (color ='lightgray',linestyle ='--',linewidth =0.5 )
            plt .xticks (rotation =45 )
            plt .tight_layout ()
        plt .savefig (activity_plot_path ,facecolor ='white')
        plt .close ()
        recommendations =[]
        if not daily_activity .empty :
            peak_day =daily_activity .idxmax ()
            recommendations .append (
            f"📅 Пик активности постов: {peak_day .strftime ('%Y-%m-%d')} ({daily_activity .max ()} постов).")
        if participants >0 :
            if engagement_rate >15 :
                recommendations .append (f"🎯 Уровень вовлеченности (ER): {engagement_rate :.2f}% - Отлично!")
            elif engagement_rate >7 :
                recommendations .append (f"🎯 Уровень вовлеченности (ER): {engagement_rate :.2f}% - Хорошо.")
            elif engagement_rate >2 :
                recommendations .append (f"🎯 Уровень вовлеченности (ER): {engagement_rate :.2f}% - Нормально.")
            else :
                recommendations .append (
                f"🎯 Уровень вовлеченности (ER): {engagement_rate :.2f}% - Низкий. Попробуйте более интерактивный контент.")
        else :
            recommendations .append (f"🎯 Уровень вовлеченности (ER): Н/Д (0 подписчиков).")
        avg_posts_per_day =daily_activity .mean ()if not daily_activity .empty else 0
        recommendations .append (f"🗓️ В среднем постов в день: {avg_posts_per_day :.2f}.")
        return wordcloud_path ,activity_plot_path ,recommendations
    def generate_hourly_insights (self ,df ):
        hourly_activity =df ['date'].dt .hour .value_counts ().sort_index ()
        hourly_plot_path ="hourly_plot.png"
        plt .figure (figsize =(12 ,6 ))
        if hourly_activity .empty :
            plt .text (0.5 ,0.5 ,"Нет данных для отображения часовой активности",ha ='center',va ='center',fontsize =16 )
            plt .axis ('off')
        else :
            plt .bar (hourly_activity .index ,hourly_activity .values ,color ='teal')
            plt .xticks (range (0 ,24 ))
            plt .xlabel ('Час суток',fontsize =14 )
            plt .ylabel ('Количество постов',fontsize =14 )
            plt .title ('Активность постов по часам суток',fontsize =16 )
            plt .grid (axis ='y',alpha =0.5 )
            plt .tight_layout ()
        plt .savefig (hourly_plot_path ,facecolor ='white')
        plt .close ()
        return hourly_plot_path