import os
import pandas as pd
from datetime import datetime
from collections import Counter
from PyQt5 .QtWidgets import (
QMainWindow ,QLabel ,QLineEdit ,QPushButton ,QVBoxLayout ,
QWidget ,QTextEdit ,QProgressBar ,QMessageBox ,QTabWidget ,QTableWidget ,QTableWidgetItem ,
QFormLayout ,QFileDialog ,QSpinBox ,QHBoxLayout ,QGroupBox ,QGridLayout ,
QInputDialog ,QMenuBar ,QAction
)
from PyQt5 .QtCore import Qt ,pyqtSignal
from PyQt5 .QtGui import QFont ,QPixmap ,QIcon
from analyzer_thread import AnalyzerThread
from analysis_helpers import analyze_sentiment ,get_emoji_stats ,normalize_text
from config import DEFAULT_STYLE ,DARK_STYLE ,emoji ,russian_stopwords
class MainWindow (QMainWindow ):
    user_input_signal =pyqtSignal (str )
    def __init__ (self ):
        super ().__init__ ()
        base_dir =os .path .dirname (os .path .abspath (__file__ ))
        icon_path =os .path .join (base_dir ,"icon.png")
        if os .path .exists (icon_path ):
            self .setWindowIcon (QIcon (icon_path ))
        self .setWindowTitle ("📊 Телеграф Анализатор")
        self .resize (1280 ,850 )
        self .current_result =None
        self .is_dark_theme =False
        self ._default_style_captured =False
        self .init_ui ()
        self .apply_styles (DEFAULT_STYLE )
    def prompt_user_input (self ,title ,label ):
        text ,ok =QInputDialog .getText (self ,title ,label ,QLineEdit .Normal )
        if ok :
            self .user_input_signal .emit (text )
        else :
            self .user_input_signal .emit ("")
    def init_ui (self ):
        self .create_menu ()
        container =QWidget ()
        main_layout =QVBoxLayout (container )
        self .tabs =QTabWidget ()
        self .analysis_tab =QWidget ()
        self .wordcloud_tab =QWidget ()
        self .activity_tab =QWidget ()
        self .hourly_tab =QWidget ()
        self .comments_tab =QWidget ()
        self .audience_tab =QWidget ()
        self .emoji_tab =QWidget ()
        self .tabs .addTab (self .analysis_tab ,"🔍 Анализ")
        self .tabs .addTab (self .wordcloud_tab ,"☁️ Облако слов")
        self .tabs .addTab (self .activity_tab ,"📈 Активность (Дни)")
        self .tabs .addTab (self .hourly_tab ,"⏰ Активность (Часы)")
        self .tabs .addTab (self .comments_tab ,"💬 Комментарии")
        self .tabs .addTab (self .audience_tab ,"👥 Активность Аудитории")
        self .tabs .addTab (self .emoji_tab ,"📊 Статистика эмодзи")
        self .init_analysis_tab ()
        self .init_wordcloud_tab ()
        self .init_activity_tab ()
        self .init_hourly_tab ()
        self .init_comments_tab ()
        self .init_audience_tab ()
        self .init_emoji_tab ()
        main_layout .addWidget (self .tabs )
        watermark_label =QLabel ("Разработано Magerko | Telegram: @magerkopython",self )
        watermark_label .setAlignment (Qt .AlignCenter )
        font =QFont ("Arial",10 ,QFont .Bold )
        watermark_label .setFont (font )
        main_layout .addWidget (watermark_label )
        self .setCentralWidget (container )
    def create_menu (self ):
        menubar =self .menuBar ()
        view_menu =menubar .addMenu ("Вид")
        toggle_theme_action =QAction ("Переключить Темную/Светлую Тему",self )
        toggle_theme_action .triggered .connect (self .toggle_theme )
        view_menu .addAction (toggle_theme_action )
    def init_analysis_tab (self ):
        layout =QVBoxLayout ()
        form_group =QGroupBox ("Параметры анализа")
        form_layout =QFormLayout ()
        self .api_id_input =QLineEdit ()
        self .api_id_input .setPlaceholderText ("Ваш Telegram API ID")
        self .api_hash_input =QLineEdit ()
        self .api_hash_input .setPlaceholderText ("Ваш Telegram API Hash")
        self .api_hash_input .setEchoMode (QLineEdit .Password )
        self .username_input =QLineEdit ()
        self .username_input .setPlaceholderText ("Пример: my_channel или https://t.me/my_channel")
        self .start_date_input =QLineEdit ()
        self .start_date_input .setPlaceholderText ("ГГГГ-ММ-ДД (необязательно)")
        self .end_date_input =QLineEdit ()
        self .end_date_input .setPlaceholderText ("ГГГГ-ММ-ДД (необязательно)")
        self .limit_spin =QSpinBox ()
        self .limit_spin .setMinimum (10 )
        self .limit_spin .setMaximum (10000 )
        self .limit_spin .setValue (200 )
        self .limit_spin .setToolTip ("Максимальное количество постов для анализа.")
        self .limit_comments_spin =QSpinBox ()
        self .limit_comments_spin .setMinimum (0 )
        self .limit_comments_spin .setMaximum (500 )
        self .limit_comments_spin .setValue (50 )
        self .limit_comments_spin .setToolTip ("Макс. комментариев для загрузки на один пост (0 - не загружать).")
        form_layout .addRow ("🔐 Идентификатор API:",self .api_id_input )
        form_layout .addRow ("🔐 Хэш API:",self .api_hash_input )
        form_layout .addRow (QLabel ())
        form_layout .addRow ("🔗 Username/Ссылка канала:",self .username_input )
        form_layout .addRow ("📅 Дата начала:",self .start_date_input )
        form_layout .addRow ("📅 Дата конца:",self .end_date_input )
        form_layout .addRow ("🔢 Лимит постов:",self .limit_spin )
        form_layout .addRow ("💬 Лимит коммент./пост:",self .limit_comments_spin )
        form_group .setLayout (form_layout )
        buttons_layout =QHBoxLayout ()
        self .start_button =QPushButton ("🚀 Начать анализ")
        self .start_button .clicked .connect (self .start_analysis )
        self .start_button .setFixedHeight (40 )
        self .save_button =QPushButton ("💾 Сохранить отчет")
        self .save_button .clicked .connect (self .save_report )
        self .save_button .setEnabled (False )
        self .save_button .setFixedHeight (40 )
        buttons_layout .addWidget (self .start_button )
        buttons_layout .addWidget (self .save_button )
        self .progress_label =QLabel ("⏳ Ожидание ввода данных...")
        self .progress_bar =QProgressBar ()
        self .progress_bar .setValue (0 )
        self .output_area =QTextEdit ()
        self .output_area .setReadOnly (True )
        font =QFont ("Arial",10 )
        self .output_area .setFont (font )
        layout .addWidget (form_group )
        layout .addLayout (buttons_layout )
        layout .addWidget (self .progress_label )
        layout .addWidget (self .progress_bar )
        layout .addWidget (self .output_area ,1 )
        self .analysis_tab .setLayout (layout )
    def init_generic_image_tab (self ,tab_widget ,graph_label_attr_name ):
        layout =QVBoxLayout ()
        graph_label =QLabel ()
        graph_label .setAlignment (Qt .AlignCenter )
        graph_label .setScaledContents (True )
        setattr (self ,graph_label_attr_name ,graph_label )
        layout .addWidget (graph_label )
        tab_widget .setLayout (layout )
    def init_wordcloud_tab (self ):
        self .init_generic_image_tab (self .wordcloud_tab ,"graph_wordcloud")
    def init_activity_tab (self ):
        self .init_generic_image_tab (self .activity_tab ,"graph_activity")
    def init_hourly_tab (self ):
        self .init_generic_image_tab (self .hourly_tab ,"graph_hourly")
    def init_audience_tab (self ):
        self .init_generic_image_tab (self .audience_tab ,"graph_audience")
        self .graph_audience .setText ("Данные по активности аудитории (на основе комментариев) появятся здесь.")
    def init_comments_tab (self ):
        layout =QVBoxLayout ()
        self .comments_info_label =QLabel ("Информация по комментариям появится здесь.")
        self .comments_info_label .setAlignment (Qt .AlignTop |Qt .AlignLeft )
        self .comments_info_label .setWordWrap (True )
        layout .addWidget (self .comments_info_label )
        self .comments_table =QTableWidget ()
        self .comments_table .setColumnCount (2 )
        self .comments_table .setHorizontalHeaderLabels (["Слово (лемма)","Частота"])
        layout .addWidget (self .comments_table )
        self .comments_example_box =QGroupBox ("Примеры комментариев по тональности")
        example_layout =QGridLayout ()
        self .positive_comments_text =QTextEdit ()
        self .positive_comments_text .setReadOnly (True )
        self .neutral_comments_text =QTextEdit ()
        self .neutral_comments_text .setReadOnly (True )
        self .negative_comments_text =QTextEdit ()
        self .negative_comments_text .setReadOnly (True )
        for i ,(label_text ,text_widget )in enumerate ([
        ("Позитивные:",self .positive_comments_text ),
        ("Нейтральные:",self .neutral_comments_text ),
        ("Негативные:",self .negative_comments_text )
        ]):
            example_layout .addWidget (QLabel (label_text ),0 ,i )
            example_layout .addWidget (text_widget ,1 ,i )
            text_widget .setPlaceholderText ("Нет примеров")
        self .comments_example_box .setLayout (example_layout )
        layout .addWidget (self .comments_example_box )
        self .comments_tab .setLayout (layout )
    def init_emoji_tab (self ):
        layout =QVBoxLayout ()
        main_splitter =QHBoxLayout ()
        posts_emoji_group =QGroupBox ("Emoji в постах (топ-15)")
        posts_emoji_layout =QVBoxLayout ()
        self .posts_emoji_table =QTableWidget ()
        self .posts_emoji_table .setColumnCount (2 )
        self .posts_emoji_table .setHorizontalHeaderLabels (["Emoji","Частота"])
        posts_emoji_layout .addWidget (self .posts_emoji_table )
        posts_emoji_group .setLayout (posts_emoji_layout )
        main_splitter .addWidget (posts_emoji_group )
        comments_emoji_group =QGroupBox ("Emoji в комментариях (топ-15)")
        comments_emoji_layout =QVBoxLayout ()
        self .comments_emoji_table =QTableWidget ()
        self .comments_emoji_table .setColumnCount (2 )
        self .comments_emoji_table .setHorizontalHeaderLabels (["Emoji","Частота"])
        comments_emoji_layout .addWidget (self .comments_emoji_table )
        comments_emoji_group .setLayout (comments_emoji_layout )
        main_splitter .addWidget (comments_emoji_group )
        layout .addLayout (main_splitter )
        self .emoji_tab .setLayout (layout )
    def apply_styles (self ,style_sheet ):
        if not self .is_dark_theme and not self ._default_style_captured :
            self ._default_style_captured =True
        self .setStyleSheet (style_sheet )
        tab_style_light ="""            QTabWidget::pane {
                            граница: сплошная 1 пиксель
                            фон: белый;
                        }
                        QTabBar::tab {
                            фон: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                        остановка: 0
                                                        остановка: 0,5
                            граница: сплошная 1 пиксель
                            цвет нижней границы:
                            граница-верхний левый радиус: 4 пикселя;
                            граница-верхний-правый-радиус: 4 пикселя;
                            минимальная ширина: 8ex;
                            отступы: 6 пикселей 10 пикселей;
                            поле справа: 2 пикселя;
                        }
                        QTabBar::tab:selected, QTabBar::tab:hover {
                            фон: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                        остановка: 0
                                                        остановка: 0,5
                        }
                        QTabBar::tab:selected {
                            цвет границы:
                            цвет нижней границы:
                        }
                        QTabBar::tab:!selected {
                            поле сверху: 2 пикселя;
                        }"""
        if self .is_dark_theme :
            self .tabs .setStyleSheet ("")
        else :
            self .tabs .setStyleSheet (tab_style_light )
    def toggle_theme (self ):
        self .is_dark_theme =not self .is_dark_theme
        if self .is_dark_theme :
            self .apply_styles (DARK_STYLE )
        else :
            self .apply_styles (DEFAULT_STYLE if self ._default_style_captured else QApplication .instance ().styleSheet ())
    def start_analysis (self ):
        api_id =self .api_id_input .text ().strip ()
        api_hash =self .api_hash_input .text ().strip ()
        username_raw =self .username_input .text ().strip ()
        start_date =self .start_date_input .text ().strip ()
        end_date =self .end_date_input .text ().strip ()
        limit_messages =self .limit_spin .value ()
        limit_comments_per_post =self .limit_comments_spin .value ()
        if not api_id or not api_hash :
            QMessageBox .warning (self ,"Ошибка ввода","Пожалуйста, введите API ID и API Hash.")
            return
        try :
            int (api_id )
        except ValueError :
            QMessageBox .warning (self ,"Ошибка ввода","API ID должен быть числом.")
            return
        username =username_raw .split ('/')[-1 ].replace ('@','')if username_raw else ""
        if not username :
            QMessageBox .warning (self ,"Ошибка ввода","Введите username или ссылку на канал!")
            return
        self .progress_label .setText ("⏳ Запуск анализа...")
        self .progress_bar .setValue (0 )
        self .output_area .clear ()
        self .save_button .setEnabled (False )
        self .clear_previous_results ()
        self .thread =AnalyzerThread (api_id ,api_hash ,username ,start_date ,end_date ,limit_messages ,
        limit_comments_per_post ,self )
        self .thread .progress_signal .connect (self .update_status )
        self .thread .result_signal .connect (self .display_results )
        self .thread .error_signal .connect (self .handle_error )
        self .thread .finished .connect (self .analysis_finished )
        self .start_button .setEnabled (False )
        self .thread .start ()
    def clear_previous_results (self ):
        self .graph_wordcloud .clear ()
        self .graph_wordcloud .setText ("Облако слов появится здесь.")
        self .graph_activity .clear ()
        self .graph_activity .setText ("График дневной активности появится здесь.")
        self .graph_hourly .clear ()
        self .graph_hourly .setText ("График часовой активности появится здесь.")
        self .graph_audience .setText ("Данные по активности аудитории (на основе комментариев) появятся здесь.")
        self .graph_audience .setPixmap (QPixmap ())
        self .comments_info_label .setText ("Информация по комментариям появится здесь.")
        self .comments_table .setRowCount (0 )
        self .positive_comments_text .clear ()
        self .neutral_comments_text .clear ()
        self .negative_comments_text .clear ()
        self .posts_emoji_table .setRowCount (0 )
        self .comments_emoji_table .setRowCount (0 )
        if self .current_result :
            for key in ["wordcloud_path","activity_plot_path","hourly_plot_path","audience_hourly_plot_path"]:
                if key in self .current_result and self .current_result [key ]and os .path .exists (self .current_result [key ]):
                    try :
                        os .remove (self .current_result [key ])
                    except OSError as e :
                        print (f"Error deleting temp file {self .current_result [key ]}: {e }")
        self .current_result =None
    def update_status (self ,status ):
        self .progress_label .setText (f"⏳ {status }")
        current_value =self .progress_bar .value ()
        if "Обработка комментариев для поста"in status :
            parts =status .split ('/')
            if len (parts )==2 and " "in parts [0 ]:
                try :
                    current_post_str =parts [0 ].split (" ")[-1 ]
                    total_posts_str =parts [1 ].split (" ")[0 ]
                    current_post =int (current_post_str )
                    total_posts =int (total_posts_str )
                    if total_posts >0 :
                        progress =60 +int (30 *(current_post /total_posts ))
                        self .progress_bar .setValue (progress )
                    return
                except ValueError :
                    pass
        elif "Сбор сообщений"in status :
            self .progress_bar .setValue (30 )
        elif "Получение данных о канале"in status :
            self .progress_bar .setValue (20 )
        elif "Подключение к Telegram"in status :
            self .progress_bar .setValue (10 )
        elif "Генерация отчетов"in status :
            self .progress_bar .setValue (95 )
        else :
            if current_value <90 :self .progress_bar .setValue (min (current_value +5 ,90 ))
    def handle_error (self ,message ):
        QMessageBox .critical (self ,"Ошибка Анализа",message )
        self .progress_label .setText (f"❌ Ошибка: {message .split ('.')[0 ]}")
        self .progress_bar .setValue (0 )
        self .start_button .setEnabled (True )
        self .save_button .setEnabled (False )
    def analysis_finished (self ):
        self .start_button .setEnabled (True )
        if self .progress_bar .value ()!=100 and not self .current_result :
            if "Ошибка"not in self .progress_label .text ():
                self .progress_label .setText ("⏹️ Анализ завершен (возможно, с проблемами).")
    def display_results (self ,result ):
        self .progress_label .setText ("✅ Анализ успешно завершен!")
        self .progress_bar .setValue (100 )
        self .save_button .setEnabled (True )
        self .current_result =result
        self .output_area .clear ()
        self .output_area .append (f"<p>👥 <b>Подписчиков:</b> {result ['participants']}</p>")
        self .output_area .append (f"<p>👁️‍🗨️ <b>Средние просмотры на пост:</b> {result ['average_views']:.2f}</p>")
        self .output_area .append (f"<p>📊 <b>Вовлеченность (ER):</b> {result ['engagement_rate']:.2f}%</p>")
        self .output_area .append (f"<p>👍 <b>Среднее реакций на пост:</b> {result ['average_reactions']:.2f}</p>")
        self .output_area .append (
        f"<p>💬 <b>Среднее комментариев (из данных поста):</b> {result ['average_comments_from_posts']:.2f}</p><br>")
        self .output_area .append ("<p>💡 <b>Рекомендации:</b></p>")
        if result ["recommendations"]:
            for rec in result ["recommendations"]:
                self .output_area .append (f"<p style='margin-left: 15px;'>👉 {rec }</p>")
        else :
            self .output_area .append ("<p style='margin-left: 15px;'>Нет специфических рекомендаций.</p>")
        self .update_image_tab (self .graph_wordcloud ,result ["wordcloud_path"],"Облако слов не может быть отображено.")
        self .update_image_tab (self .graph_activity ,result ["activity_plot_path"],
        "График активности не может быть отображен.")
        self .update_image_tab (self .graph_hourly ,result ["hourly_plot_path"],
        "График часовой активности не может быть отображен.")
        self .display_comment_analysis (result ["comments_df"])
        self .display_emoji_stats (result ["df"],result ["comments_df"])
        self .tabs .setCurrentIndex (0 )
    def update_image_tab (self ,graph_label_widget ,image_path ,error_message ):
        if image_path and os .path .exists (image_path ):
            pixmap =QPixmap (image_path )
            if not pixmap .isNull ():
                graph_label_widget .setPixmap (pixmap )
            else :
                graph_label_widget .setText (f"{error_message } (Ошибка загрузки изображения)")
        else :
            graph_label_widget .setText (error_message )
    def display_comment_analysis (self ,comments_df ):
        self .positive_comments_text .clear ()
        self .neutral_comments_text .clear ()
        self .negative_comments_text .clear ()
        self .comments_table .setRowCount (0 )
        if comments_df is None or comments_df .empty :
            self .comments_info_label .setText (
            "Нет комментариев для анализа, или они не были загружены.\nУбедитесь, что у канала есть связанный чат для обсуждений, и лимит комментариев > 0.")
            self .graph_audience .setText ("Нет комментариев для анализа активности аудитории.")
            self .graph_audience .setPixmap (QPixmap ())
            return
        comments_df ['sentiment']=comments_df ['comment'].apply (analyze_sentiment )
        pos_count =(comments_df ['sentiment']=='positive').sum ()
        neg_count =(comments_df ['sentiment']=='negative').sum ()
        neu_count =(comments_df ['sentiment']=='neutral').sum ()
        total_comments_analyzed =len (comments_df )
        info_text_html =(f"<p><b>Анализ комментариев ({total_comments_analyzed } загружено):</b><br>"
        f"🟢 Позитивных: {pos_count } ({pos_count /total_comments_analyzed :.1%})<br>"
        f"🔴 Негативных: {neg_count } ({neg_count /total_comments_analyzed :.1%})<br>"
        f"⚪ Нейтральных: {neu_count } ({neu_count /total_comments_analyzed :.1%})</p>"
        "<p><b>Ключевые слова в комментариях (топ-10 лемм):</b></p>")
        self .comments_info_label .setText (info_text_html )
        all_comment_words_normalized =[]
        for text in comments_df ['comment'].dropna ():
            all_comment_words_normalized .extend (normalize_text (text ))
        filtered_comment_words =[w for w in all_comment_words_normalized if w not in russian_stopwords and len (w )>2 ]
        word_counts =Counter (filtered_comment_words )
        top_comment_words =word_counts .most_common (10 )
        self .comments_table .setRowCount (len (top_comment_words ))
        for i ,(word ,freq )in enumerate (top_comment_words ):
            self .comments_table .setItem (i ,0 ,QTableWidgetItem (word ))
            self .comments_table .setItem (i ,1 ,QTableWidgetItem (str (freq )))
        self .comments_table .resizeColumnsToContents ()
        def show_examples (sent_type ,text_edit_widget ):
            examples =comments_df [comments_df ['sentiment']==sent_type ]['comment'].head (5 )
            if not examples .empty :
                text_edit_widget .setHtml (
                "<br>".join ([f"- <i>{ex .replace ('<','&lt;').replace ('>','&gt;')}</i>"for ex in examples ]))
            else :
                text_edit_widget .setPlaceholderText (f"Нет {sent_type } комментариев")
        show_examples ('positive',self .positive_comments_text )
        show_examples ('neutral',self .neutral_comments_text )
        show_examples ('negative',self .negative_comments_text )
        hourly_comments =comments_df ['date'].dt .hour .value_counts ().sort_index ()
        audience_plot_path ="audience_hourly_plot.png"
        if self .current_result :
            self .current_result ["audience_hourly_plot_path"]=audience_plot_path
        if not hourly_comments .empty :
            import matplotlib .pyplot as plt
            plt .figure (figsize =(12 ,6 ))
            plt .bar (hourly_comments .index ,hourly_comments .values ,color ='forestgreen')
            plt .xticks (range (0 ,24 ))
            plt .xlabel ('Час суток',fontsize =14 )
            plt .ylabel ('Комментариев в час',fontsize =14 )
            plt .title ('Активность аудитории по часам (комментарии)',fontsize =16 )
            plt .grid (axis ='y',alpha =0.5 )
            plt .tight_layout ()
            plt .savefig (audience_plot_path ,facecolor ='white')
            plt .close ()
            self .update_image_tab (self .graph_audience ,audience_plot_path ,
            "График активности аудитории не может быть отображен.")
        else :
            self .graph_audience .setText ("Недостаточно данных для отображения активности аудитории (комментарии).")
            self .graph_audience .setPixmap (QPixmap ())
    def display_emoji_stats (self ,posts_df ,comments_df ):
        self .posts_emoji_table .setRowCount (0 )
        self .comments_emoji_table .setRowCount (0 )
        if emoji is None :
            self .posts_emoji_table .setRowCount (1 )
            self .posts_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Библиотека 'emoji' не найдена."))
            self .posts_emoji_table .setSpan (0 ,0 ,1 ,2 )
            self .comments_emoji_table .setRowCount (1 )
            self .comments_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Библиотека 'emoji' не найдена."))
            self .comments_emoji_table .setSpan (0 ,0 ,1 ,2 )
            return
        if posts_df is not None and not posts_df .empty :
            post_emojis =get_emoji_stats (posts_df ['message'])
            self .posts_emoji_table .setRowCount (len (post_emojis )if post_emojis else 1 )
            if post_emojis :
                for i ,(em ,freq )in enumerate (post_emojis ):
                    self .posts_emoji_table .setItem (i ,0 ,QTableWidgetItem (em ))
                    self .posts_emoji_table .setItem (i ,1 ,QTableWidgetItem (str (freq )))
            else :
                self .posts_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Emoji в постах не найдены."))
                self .posts_emoji_table .setSpan (0 ,0 ,1 ,2 )
            self .posts_emoji_table .resizeColumnsToContents ()
        else :
            self .posts_emoji_table .setRowCount (1 )
            self .posts_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Нет постов для анализа emoji."))
            self .posts_emoji_table .setSpan (0 ,0 ,1 ,2 )
        if comments_df is not None and not comments_df .empty :
            comment_emojis =get_emoji_stats (comments_df ['comment'])
            self .comments_emoji_table .setRowCount (len (comment_emojis )if comment_emojis else 1 )
            if comment_emojis :
                for i ,(em ,freq )in enumerate (comment_emojis ):
                    self .comments_emoji_table .setItem (i ,0 ,QTableWidgetItem (em ))
                    self .comments_emoji_table .setItem (i ,1 ,QTableWidgetItem (str (freq )))
            else :
                self .comments_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Emoji в комментариях не найдены."))
                self .comments_emoji_table .setSpan (0 ,0 ,1 ,2 )
            self .comments_emoji_table .resizeColumnsToContents ()
        else :
            self .comments_emoji_table .setRowCount (1 )
            self .comments_emoji_table .setItem (0 ,0 ,QTableWidgetItem ("Нет комментариев для анализа emoji."))
            self .comments_emoji_table .setSpan (0 ,0 ,1 ,2 )
    def save_report (self ):
        if not self .current_result or self .current_result ["df"].empty :
            QMessageBox .information (self ,"Сохранение отчета","Нет данных для сохранения.")
            return
        df_to_save =self .current_result ["df"]
        channel_name_raw =self .username_input .text ().strip ().split ('/')[-1 ].replace ('@','')
        channel_name_safe ="".join (c if c .isalnum ()else "_"for c in channel_name_raw )or "unknown_channel"
        default_filename =f"{channel_name_safe }_report_{datetime .now ().strftime ('%Y%m%d_%H%M%S')}"
        save_path_csv ,_ =QFileDialog .getSaveFileName (self ,"Сохранить CSV отчет",f"{default_filename }.csv",
        "CSV-файлы (*.csv)")
        if save_path_csv :
            try :
                df_to_save .to_csv (save_path_csv ,index =False ,encoding ='utf-8-sig')
                text_report_path =save_path_csv .replace ('.csv','_summary.txt')
                with open (text_report_path ,'w',encoding ='utf-8')as f :
                    f .write (f"Отчет по Telegram-каналу: {channel_name_raw }\n")
                    f .write (f"Дата генерации: {datetime .now ().strftime ('%Y-%m-%d %H:%M:%S')}\n\n")
                    f .write ("--- ОСНОВНЫЕ ПОКАЗАТЕЛИ ---\n")
                    temp_doc_output =QTextEdit ()
                    temp_doc_output .setHtml (self .output_area .toHtml ())
                    f .write (temp_doc_output .toPlainText ())
                    if "comments_df"in self .current_result and not self .current_result ["comments_df"].empty :
                        f .write ("\n\n--- АНАЛИЗ КОММЕНТАРИЕВ ---\n")
                        temp_doc_comments =QTextEdit ()
                        temp_doc_comments .setHtml (self .comments_info_label .text ())
                        f .write (temp_doc_comments .toPlainText ())
                        f .write ("\nТоп слова в комментариях:\n")
                        for r in range (self .comments_table .rowCount ()):
                            word =self .comments_table .item (r ,0 ).text ()
                            freq =self .comments_table .item (r ,1 ).text ()
                            f .write (f"  {word }: {freq }\n")
                    if emoji and "df"in self .current_result :
                        f .write ("\n\n--- СТАТИСТИКА ЭМОДЗИ ---")
                        post_emojis =get_emoji_stats (self .current_result ["df"]['message'])
                        f .write ("\nЛучшие эмодзи в сообщениях:\n")
                        if post_emojis :
                            for em ,freq in post_emojis :f .write (f"  {em } : {freq }\n")
                        else :
                            f .write ("  Нет Emoji в постах.\n")
                        if "comments_df"in self .current_result and not self .current_result ["comments_df"].empty :
                            comment_emojis =get_emoji_stats (self .current_result ["comments_df"]['comment'])
                            f .write ("\nТоп Emoji в комментариях:\n")
                            if comment_emojis :
                                for em ,freq in comment_emojis :f .write (f"  {em } : {freq }\n")
                            else :
                                f .write ("  Нет Emoji в комментариях.\n")
                        else :
                            f .write ("  Нет комментариев для анализа Emoji.\n")
                QMessageBox .information (self ,"Сохранение отчета",
                f"Отчеты сохранены:\n{save_path_csv }\n{text_report_path }")
            except Exception as e :
                QMessageBox .critical (self ,"Ошибка сохранения",f"Не удалось сохранить отчет: {e }")
    def closeEvent (self ,event ):
        self .clear_previous_results ()
        event .accept ()