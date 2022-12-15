import requests
from concurrent.futures import ThreadPoolExecutor, wait
from bs4 import BeautifulSoup as bs
import os
import json
import time

import HardwareParser

''' Settings '''
csv_path = "SteamData.csv" # (Relative) Path to the output file that is being generated / overwritten
batches = 256 # How many chunks of games (size ~50) to pull from Steam
multithreaded = True # Whether to use multithreading to speed things up. Disabling multithreading is good for debugging.
max_workers = 16 # For multithreading: Maximum number of threads to be created within the ThreadPoolExecutor
verbose = True # Whether to log stuff to stdout

def main():
    if verbose:
        start_time = time.time()
        print("\nStarting\n")

    if verbose: print(f"\nPreparing csv file [{time.time() - start_time}s]\n")
    prepare_csv_file()

    if verbose: print(f"\nGetting games and data [{time.time() - start_time}s]\n")
    if multithreaded:
        '''
        Process:
        1) Get games within this batch by sending a request to Steam (single-threaded)
        2) Get data for every game within this batch by scraping its Steam page (multithreaded)
        3) Wait for all these tasks to complete
        4) Append all data from this batch to the csv file
        5) Repeat for all batches
        '''
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, batches):
                game_infos = [] # List of dicts with all the data for every game
                futures = [] # To keep track of the progress of the Executor
                if verbose: print(f"\nGetting games in batch {i} [{time.time() - start_time}s]\n")
                get_games(game_infos, i) # !
                if verbose: print(f"\nGetting data for games in batch {i} [{time.time() - start_time}s]\n")
                for game_info in game_infos:
                    futures.append(executor.submit(get_more_data, game_info)) # !
                wait(futures) # Wait until this batch is fully processed
                if verbose: print(f"\nWriting data to file [{time.time() - start_time}s]\n")
                write_data_to_csv_file(game_infos)
    else:
        '''
        Process:
        1) Get games within this batch by sending a request to Steam
        2) Get data for every game within this batch by scraping its Steam page
        3) Append all data from this batch to the csv file
        4) Repeat for all batches
        '''
        for i in range(0, batches):
            game_infos = [] # List of dicts with all the data for every game
            if verbose: print(f"\nGetting games in batch {i} [{time.time() - start_time}s]\n")
            get_games(game_infos, i) # !
            if verbose: print(f"\nGetting data for games in batch {i} [{time.time() - start_time}s]\n")
            for game_info in game_infos:
                get_more_data(game_info) # !
            write_data_to_csv_file(game_infos)

    if verbose: print(f"\nFinished after {time.time() - start_time} seconds\n")

# ----------------------------------------

def get_games(game_info : dict, offset : int):
    '''
    Sends a request to Steam and scrapes the Steam search page to get a batch of games.
    Writes "name" and "url" directly into game_infos.
    '''
    link = f"https://store.steampowered.com/search/results/?query=&start={offset*50}&count=50&dynamic_data=&sort_by=_ASC&os=win&snr=1_7_7_7000_7&filter=topsellers&infinite=1"
    listPageRequest = requests.get(link)
    html = json.loads(listPageRequest.content)["results_html"]
    listPageSoup = bs(html, "lxml")
    gameRows = listPageSoup.find_all("a", {"class" : "search_result_row ds_collapse_flag"})
    for gameRow in gameRows:
        game_name_span = gameRow.find("span", {"class" : "title"})
        game_info.append( 
            { "name" : game_name_span.string,
              "url"  : gameRow["href"] } 
        )

# ----------------------------------------
def get_more_data(game_info : dict):
    '''
    Retrieves much more data about each game in game_info by
    scraping their Steam pages.
    Writes directly to game_info.
    '''
    game_page_request = requests.get(game_info["url"])
    game_page_soup = bs(game_page_request.content, "lxml")

    get_price(game_info, game_page_soup)
    get_release_date(game_info, game_page_soup)
    get_sys_reqs(game_info, game_page_soup)
    get_ratings(game_info, game_page_soup)
    get_genre(game_info, game_page_soup)

def get_price(game_info : dict, game_page_soup : bs):
    price_div = game_page_soup.find("div", {"class" : "game_purchase_price price"})
    if price_div != None:
        price = price_div.text.strip() # strip is important
        if price.lower() == "free to play":
            price = "0"
            game_info["price"] = price
            return
        price = price.replace(price[-1], "")
        price = price.replace(",", ".")
        if not all(map(lambda s: s.isnumeric(), price.split("."))):
            price = ""
        game_info["price"] = price
    else:
        price_div = game_page_soup.find("div", {"class" : "discount_original_price"})
        if price_div != None:
            price = price_div.text.strip() # strip is important
            if price.lower() == "free to play":
                price = "0"
                game_info["price"] = price
                return
            price = price.replace(price[-1], "")
            price = price.replace(",", ".")
            if not all(map(lambda s: s.isnumeric(), price.split("."))):
                price = ""
            game_info["price"] = price

def get_release_date(game_info : dict, game_page_soup : bs):
    release_date_div = game_page_soup.select_one(".release_date .date")
    if release_date_div != None:
        game_info["release_date"] = release_date_div.string

def get_sys_reqs(game_info : dict, game_page_soup : bs):
    game_info["sys_reqs_min"] = {"OS" : "", "Processor" : "", "Graphics" : "", "Memory" : "", "Storage" : ""}
    game_info["sys_reqs_rec"] = {"OS" : "", "Processor" : "", "Graphics" : "", "Memory" : "", "Storage" : ""}
    sys_req_div = game_page_soup.find("div", {"class" : "game_area_sys_req sysreq_content active", "data-os" : "win"})
    if sys_req_div == None:
        return
    min_col = sys_req_div.select_one(".game_area_sys_req_leftCol")
    rec_col = sys_req_div.select_one(".game_area_sys_req_rightCol")
    if min_col != None:
        min_items = min_col.find_all("li")
        if min_items != None:
            for item in min_items:
                reqStrs = item.get_text().split(":")
                if (len(reqStrs) == 2):
                    game_info["sys_reqs_min"][reqStrs[0].strip()] = reqStrs[1].strip()
    if rec_col != None:
        rec_items = rec_col.find_all("li")
        if rec_items != None:
            for item in rec_items:
                reqStrs = item.get_text().split(":")
                if (len(reqStrs) == 2):
                    game_info["sys_reqs_rec"][reqStrs[0].strip()] = reqStrs[1].strip()

def get_ratings(game_info : dict, game_page_soup : bs):
    ratings_meta = game_page_soup.find("meta", itemprop="ratingValue")
    if ratings_meta != None:
        game_info["rating"] = ratings_meta["content"]
    ratings_count_meta = game_page_soup.find("meta", itemprop="reviewCount")
    if ratings_count_meta != None:
        game_info["ratingCount"] = ratings_count_meta["content"]

def get_genre(game_info : dict, game_page_soup : bs):
    genres_and_manufacturer_div = game_page_soup.find("div", {"id" : "genresAndManufacturer"})
    if genres_and_manufacturer_div != None:
        genres_span = genres_and_manufacturer_div.find("span")
        if genres_span != None:
            first_genre_link = genres_span.find_next("a")
            if first_genre_link != None:
                game_info["genre0"] = first_genre_link.string
                second_genre_link = first_genre_link.findNextSibling("a")
                if second_genre_link != None:
                    game_info["genre1"] = second_genre_link.string

# ----------------------------------------

def prepare_csv_file():
    '''
    Creates a new file at csv_path and writes the column headers into it
    '''
    if os.path.exists(csv_path):
        os.remove(csv_path)
    with open(csv_path, "w", encoding="utf-16") as csv_file:
        column_names = ["Name", "Price", "Release date", "Genre 1", "Genre 2", "Rating", "Rating count", "Min OS", "Min Processor", "Min Graphics", "Min Graphics NVIDIA", "Min Graphics AMD", "Min Memory", "Min Storage", "Rec OS", "Rec Processor", "Rec Graphics", "Rec Graphics NVIDIA", "Rec Graphics AMD", "Rec Memory", "Rec Storage"]
        csv_file.write(",".join(column_names) + "\n")

def write_data_to_csv_file(game_infos : list[dict]):
    '''
    Appends all data within game_infos to the csv.
    Every dict in game_infos corresponds to one row with the dict entries being the columns.
    '''
    with open(csv_path, "a", encoding="utf-16") as csv_file:
        for game_info in game_infos:
            name = game_info["name"]
            price = game_info.get("price", "")
            release_date = game_info.get("release_date", "")
            genre0 = game_info.get("genre0", "")
            genre1 = game_info.get("genre1", "")
            rating = game_info.get("rating", "")
            rating_count = game_info.get("ratingCount", "")
            min_reqs = game_info.get("sys_reqs_min", {"OS" : "", "Processor" : "", "Graphics" : "", "Memory" : "", "Storage" : ""})
            rec_reqs = game_info.get("sys_reqs_rec", {"OS" : "", "Processor" : "", "Graphics" : "", "Memory" : "", "Storage" : ""})
            min_graphics_nvidia, min_graphics_amd = "", ""
            rec_graphics_nvidia, rec_graphics_amd = "", ""
            if "Graphics" in min_reqs:
                min_graphics_nvidia, min_graphics_amd = HardwareParser.process_graphics_regex(min_reqs.get("Graphics"))
            if "Graphics" in rec_reqs:
                rec_graphics_nvidia, rec_graphics_amd = HardwareParser.process_graphics_regex(rec_reqs.get("Graphics"))
            reqs = [min_reqs.get("OS", ""), min_reqs.get("Processor", ""), min_reqs.get("Graphics", ""), min_graphics_nvidia, min_graphics_amd, min_reqs.get("Memory", ""), min_reqs.get("Storage", ""), rec_reqs.get("OS", ""), rec_reqs.get("Processor", ""), rec_reqs.get("Graphics", ""), rec_graphics_nvidia, rec_graphics_amd, rec_reqs.get("Memory", ""), rec_reqs.get("Storage", "")]
            name = name.replace('"', '""')
            genre0 = genre0.replace('"', '""')
            genre1 = genre1.replace('"', '""')
            csv_file.write(f'"{name}"')
            csv_file.write("," + f'"{price}"')
            csv_file.write("," + f'"{release_date}"')
            csv_file.write("," + f'"{genre0}"')
            csv_file.write("," + f'"{genre1}"')
            csv_file.write("," + f'"{rating}"')
            csv_file.write("," + f'"{rating_count}"')
            for (index, req) in enumerate(reqs):
                req_escaped = req.replace('"', '""')
                csv_file.write("," + f'"{req_escaped}"')
            csv_file.write("\n")
        csv_file.flush()

# ----------------------------------------

def print_info(game_infos : list[dict], key : str, key2 : str = None):
    recNameLength = max(map(lambda s: len(s), map(lambda gi: gi["name"], game_infos)))
    for game_info in game_infos:
        padding = ' ' * (recNameLength - len(game_info['name']))
        if key in game_info.keys():
            if key2 == None:
                print(f"{game_info['name']} {padding} {game_info[key]}")
            elif key2 not in game_info[key].keys():
                print(game_info['name'])
            else:
                print(f"{game_info['name']} {padding} {game_info[key][key2]}")
        else:
            print(game_info['name'])

# ----------------------------------------

if __name__ == '__main__':
    main()