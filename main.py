import gspread
from google.oauth2.service_account import Credentials
import new_scrapper

scopes = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
client = gspread.authorize(creds)

sheet_id = '1qo2CNMpsO4eLWDFzzGdzrD_ZEd4vjqYcESp2cJcZ5Vw'
sheet = client.open_by_key(sheet_id).sheet1
# Проверка на API
# values_list = sheet.row_values(1)
# print(values_list)
# sheet.append_row(values_list)
# print(sheet.row_values(2))
URL = "https://ci70535.tw1.ru/view.php?amount_videos=3&percent_bigger_5_min=60&percent_ru_videos=50&average_views=50000"

def scanning(sheet):
    try:
        column_values = sheet.col_values(1)
        return column_values
    except Exception as e:
        print(f"Error retrieving column values: {e}")
        return []


def append_result_to_sheet(sheet, result):
    try:
        values = [
        result['name'],
        result['bloger_info'],
        result['n_videos'],
        result['duration'],
        result['rus'],
        result['mean_views'],
        result['description'],
        result['links'],
        result['subscribers'],
        result['all_views'],
        result['date'],
        result['country'],
        result['mean_likes'],
        result['mean_comments'],
        result['err']
        ]
        sheet.append_row(values)
        new_scrapper.logging.info("Успешный успех")
    except Exception as e:
            new_scrapper.logging.error(f"Error appending row: {e}")
            new_scrapper.logging.error(f"Result: {result}")


bad_list = ['Украина', 'Зеленский', 'Ukraine']

scraper = new_scrapper.YouTubeScraper(URL, bad_list, sheet)



for result in scraper.start():
    print(result)
    append_result_to_sheet(sheet, result)
scraper.close()