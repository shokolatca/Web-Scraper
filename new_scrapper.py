import logging
import requests
import re
import pandas as pd
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from time import sleep

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class YouTubeScraper:
    def __init__(self, url, bad_list, sheet, scroll=1000):
        self.url = url
        self.scroll = scroll
        self.bad_list = bad_list
        self.sheet = sheet
        self.driver = self.initialize_driver()

    def initialize_driver(self):
        logging.info("Инициализация драйвера Chrome")
        options = Options()
        # options.add_argument('--headless=new')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-images')
        options.add_argument('--disable-javascript')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.page_load_strategy = 'eager'  # Загрузка страницы останавливается как только основной контент загрузилсяs
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        return driver

    def scanning(self):
        try:
            column_values = self.sheet.col_values(1)
            return column_values
        except Exception as e:
            logging.error(f"Error retrieving column values: {e}")
            return []

    def fast_zapros(self, i):
        try:
            elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, f'//tbody/tr/td[{i}]/a'))
            )
            logging.info(f"Найдено элементов: {len(elements)} по XPath //tbody/tr/td[{i}]/a")
            return elements
        except Exception as e:
            logging.error(f"Ошибка при выполнении fast_zapros: {e}")
            return []

    def bad_words(self, input_string):
        for word in self.bad_list:
            if word in input_string:
                return True
        return False

    def get_prev_table(self):
        logging.info(f"Получение таблицы с URL: {self.url}")
        try:
            response = requests.get(self.url)
            response.encoding = 'utf-8'
            html_content = StringIO(response.text)
            table = pd.read_html(html_content)
            logging.info("Таблица успешно получена")
            return table[0]
        except Exception as e:
            logging.error(f"Ошибка при получении таблицы: {e}")
            return pd.DataFrame()

    def bloger_links(self):
        logging.info(f"Получение ссылок блогеров с URL: {self.url}")
        self.driver.get(self.url)
        try:
            elements = self.fast_zapros(2)
            bloger_link = [i.get_attribute('href') for i in elements if i.get_attribute('href') is not None]
            logging.info(f"Найдено {len(bloger_link)} ссылок блогеров")
            return bloger_link
        except Exception as e:
            logging.error(f"Ошибка при получении ссылок блогеров: {e}")
            return []

    def convert_subscribers(self, subscriber_str):
        logging.info(f'subscribers {subscriber_str}')
        subscriber_str = subscriber_str.replace('подписчиков', '').replace('подписчика', '').replace('подписчик', '').replace('subscribers', '').replace('.', '')
        if "млн" in subscriber_str or 'M' in subscriber_str:
            ss = int(subscriber_str.replace('млн', '').replace('M', '').replace(',', '').replace(' ', '')) * 1000000
        elif "тыс" in subscriber_str or 'K' in subscriber_str:
            ss = int(subscriber_str.replace('тыс', '').replace('K', '').replace(',', '').replace(' ', '')) * 1000
        else:
            ss = int(subscriber_str.replace(',', '').replace(' ', ''))
        logging.info(f'subscribers {ss}')
        return ss

    def extract_views_count(self, views_str):
        try:
            logging.info(f'Extract_views_count {views_str}')
            num =  int(views_str.replace(',', '').replace(' ', '').replace('просмотров', '').replace('views', '').replace('просмотра', ''))
            logging.info(f'All views {num}')
            return num
        except Exception as e:
            logging.error("issue with extract_views_count")
            return 0

    def chanel_description(self, url):
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 40, 0.01).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.truncated-text-wiz__absolute-button'))
            ).click()
            description = WebDriverWait(self.driver, 40, 0.01).until(
                EC.presence_of_element_located((By.XPATH, "//yt-attributed-string[@id='description-container']/span[1]"))
            ).text
            logging.info("Описание успешно получено")
        except Exception as e:
            logging.error(f"Ошибка при получении описания канала: {e}")
            description = ''

        s_links = self.driver.find_elements(By.CSS_SELECTOR, '.yt-core-attributed-string__link.yt-core-attributed-string__link--call-to-action-color.yt-core-attributed-string--link-inherit-color')
        s_text = self.driver.find_elements(By.XPATH, "//tr[@class='description-item style-scope ytd-about-channel-renderer']/td[2]")

        links = {}
        for link in s_links:
            try:
                temp = link.get_attribute('href')
                temp_text = link.text
                if temp and 'javascript' not in temp:
                    links[temp_text] = temp
                logging.error("Cсылки на соц. сети успешно получены")
            except Exception as e:
                logging.error(f"Ошибка при получении ссылки канала: {e}")

        stat_inf = [stat.text for stat in s_text if stat.text]

        chanel = {}
        chanel['description'] = description
        chanel['links'] = "\n".join(list(links.values())) if links else 'No links'
        chanel['subscribers'] = self.convert_subscribers(stat_inf[-5]) if len(stat_inf) >= 3 else 'No Subscribers'
        chanel['views'] = self.extract_views_count(stat_inf[-3]) if len(stat_inf) >= 3 else 'No Views'
        chanel['date'] = stat_inf[-2] if len(stat_inf) >= 4 else 'No Date'
        chanel['country'] = stat_inf[-1] if len(stat_inf) == 7 else (stat_inf[-1] if len(stat_inf) >= 5 else 'No Country')

        return chanel

    def get_chanel_video_links(self, url):
        self.driver.get(url + '/videos')
        sleep(2)
        self.driver.execute_script("window.scrollTo(0, 1500)")
        try:
            ytb_links = WebDriverWait(self.driver, 40, 0.01).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a#thumbnail.yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail'))
            )
            ll = [ytb_links[i].get_attribute('href') for i in range(2, len(ytb_links)) if i < 8 and ytb_links[i].get_attribute('href')]
            logging.info(f'LEN:{len(ll)}')
            return ll
        except Exception as e:
            logging.error(f"Ошибка при получении видео ссылок канала: {e}")
            return []

    def video_scraper(self, url):
        logging.info(f"Запуск видео {url}")
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 40, 0.01).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.ytp-play-button.ytp-button'))
            ).click()
            logging.info("Успешно кликнули")
        except Exception as e:
            logging.error(f"Ошибка при запуске видео: {e}")
        
        try:
            WebDriverWait(self.driver, 40, 0.01).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'tp-yt-paper-button#expand'))
            ).click()
            logging.info("Успешно открыли описание ролика")
        except Exception as e:
            logging.error(f"Ошибка при раскрытии описания видео: {e}")
            
        video = {}
        try:
            views_element = WebDriverWait(self.driver, 40, 0.01).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#info-container span')))[0].text
            logging.info(f"Успешно получены views_element  '{views_element}'")
            views = views_element.split()[0].replace(',', '').replace(' ', '')
            views = int(views)
            logging.info(f"Успешно получены views {views}")
        except Exception as e:
            logging.error(f"Ошибка при получении количества просмотров: {e}")
            views = 0

        try:
            nn = WebDriverWait(self.driver, 40, 0.01).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.yt-spec-button-shape-next.yt-spec-button-shape-next--tonal.yt-spec-button-shape-next--mono.yt-spec-button-shape-next--size-m.yt-spec-button-shape-next--icon-leading.yt-spec-button-shape-next--segmented-start"))
            ).get_attribute('aria-label').replace(' ', '')

            likes = int(''.join(re.findall(r'\d+', nn)))
            logging.info(f"Успешно получены likes {likes}")
        except Exception as e:
            logging.error(f"Ошибка при получении количества лайков: {e}")
            likes = 0

        try:
            self.driver.execute_script("window.scrollTo(0, 8500)")
            comments_element = WebDriverWait(self.driver, 40, 0.01).until(
                EC.presence_of_element_located((By.XPATH, '//yt-formatted-string[@class = "count-text style-scope ytd-comments-header-renderer"]/span[1]'))
            )
            comments = comments_element.text.replace(",", "").replace(' ', '')
            comments = int(comments)
            logging.info(f"Успешно получены comments {comments}")
        except Exception as e:
            logging.error(f"Ошибка при получении количества комментариев: {e}")
            comments = 0

        try:
            title = self.driver.find_element(By.XPATH, '//yt-formatted-string[@class ="style-scope ytd-watch-metadata"]').text
            logging.info("Успешно получен title")
        except Exception as e:
            logging.error(f"Ошибка при получении заголовка видео: {e}")
            title = "No Title"

        video['title'] = title
        video['views'] = views
        video['likes'] = likes
        video['comments'] = comments
        return video

    def start(self):
        table = self.get_prev_table()
        logging.info(f'Таблица {table.columns.tolist()}')
        required_columns = ['Ссылка', 'Кол. видео', '% > 5 мин.', '% русс. видео', 'Просмотры (средн)']
        for column in required_columns:
            if column not in table.columns.tolist():
                raise ValueError(f"Колонка '{column}' отсутствует в таблице")

        try:
            bloger_list = self.bloger_links()
            if len(bloger_list) != len(table):
                raise Exception("Количество блогеров не совпадает с количеством строк в таблице.")
        except Exception as e:
            logging.error(f"Ошибка при получении списка блогеров в старт функции: {e}")

        table['bloger_info'] = bloger_list

        for index, row in table.iterrows():
            logging.info(f'Работаю с блогером {row["Ссылка"]}')
            name = row["Ссылка"]
            n_videos = row['Кол. видео']
            duration = row['% > 5 мин.']
            rus = row['% русс. видео']
            mean_views = row['Просмотры (средн)']
            bloger_info = row['bloger_info']
            if name in self.scanning():
                logging.info("Блогер уже был в таблице")
                continue

            chanel = self.chanel_description(bloger_info)

            mean_likes = 0
            mean_views = 0
            mean_comments = 0
            num_videos = 0

            if self.bad_words(chanel['description']) or self.bad_words(chanel['country']):
                logging.info('Найдены запретные слова в описании или в названии страны')
                continue

            video_links_list = self.get_chanel_video_links(bloger_info)
            for link in video_links_list:
                video = self.video_scraper(link)
                if self.bad_words(video['title']):
                    logging.info('Найдены запретные слова в названии ролика')
                    num_videos = 0
                    break
                if video:
                    mean_likes += video['likes']
                    mean_views += video['views']
                    mean_comments += video['comments']
                    num_videos +=1

            try:
                mean_likes /= num_videos
                mean_views /= num_videos
                mean_comments /= num_videos
                err = round((mean_comments + mean_likes) / mean_views, 5)
            except ZeroDivisionError:
                continue

            result_dict = {
                'name': name,
                'bloger_info': bloger_info,
                'n_videos': n_videos,
                'duration': duration,
                'rus': rus,
                'mean_views': mean_views,
                'url': bloger_info,
                'description': chanel['description'],
                'links': chanel['links'],
                'subscribers': chanel['subscribers'],
                'all_views': chanel['views'],
                'date': chanel['date'],
                'country': chanel['country'],
                'mean_likes': mean_likes,
                'mean_comments': mean_comments,
                'err': err
            }

            yield result_dict

    def close(self):
        self.driver.quit()

# Usage example with parameters, bad word list, and Google Sheet object
# Assume `sheet` is a gspread sheet object properly authenticated and loaded
# scraper = YouTubeScraper(URL, bad_words_list, sheet)
# for result in scraper.start():
#     print(result)
# scraper.close()


