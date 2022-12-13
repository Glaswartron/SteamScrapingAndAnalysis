import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup as bs
import json
import time

import HardwareParser

def main():
    start_time = time.time()
    print("\nStarting\n")

    # Get games
    print(f"\nGetting games [{time.time() - start_time}s]\n")
    game_infos = [] # List of dicts
    for i in range(0, 6):
        get_games(game_infos, i)

    # Get sys reqs, release dates, ratings and genre (see functions)
    print(f"\nGetting more data [{time.time() - start_time}s]\n")
    with ThreadPoolExecutor(max_workers=16) as executor:
        for game_info in game_infos:
            executor.submit(get_more_data, game_info)

    # Remove games with invalid infos
    print(f"\nRemoving invalid entries [{time.time() - start_time}s]\n")
    game_infos = filter(lambda gi: gi.get("sys_reqs_min") != None and gi.get("sys_reqs_rec") != None, game_infos)

    # Write csv file
    print(f"Writing csv file [{time.time() - start_time}s]")
    with open("SteamSysReqs.csv", "w", encoding="utf-16") as csv_file:
        column_names = ["Name", "Release date", "Genre 1", "Genre 2", "Rating", "Min OS", "Min Processor", "Min Graphics", "Min Graphics NVIDIA", "Min Graphics AMD", "Min Memory", "Min Storage", "Rec OS", "Rec Processor", "Rec Graphics", "Rec Graphics NVIDIA", "Rec Graphics AMD", "Rec Memory", "Rec Storage"]
        csv_file.write(",".join(column_names) + "\n")
        for game_info in game_infos:
            name = game_info["name"]
            release_date = game_info.get("release_date", "")
            genre0 = game_info.get("genre0", "")
            genre1 = game_info.get("genre1", "")
            rating = game_info.get("rating", "")
            min_reqs = game_info["sys_reqs_min"]
            rec_reqs = game_info["sys_reqs_rec"]
            min_graphics_nvidia, min_graphics_amd = "", ""
            rec_graphics_nvidia, rec_graphics_amd = "", ""
            if "Graphics" in min_reqs:
                min_graphics_nvidia, min_graphics_amd = HardwareParser.process_graphics_regex(min_reqs.get("Graphics"))
            if "Graphics" in rec_reqs:
                rec_graphics_nvidia, rec_graphics_amd = HardwareParser.process_graphics_regex(rec_reqs.get("Graphics"))
            reqs = [min_reqs.get("OS", ""), min_reqs.get("Processor", ""), min_reqs.get("Graphics", ""), min_graphics_nvidia, min_graphics_amd, min_reqs.get("Memory", ""), min_reqs.get("Storage", ""), rec_reqs.get("OS", ""), rec_reqs.get("Processor", ""), rec_reqs.get("Graphics", ""), rec_graphics_nvidia, rec_graphics_amd, rec_reqs.get("Memory", ""), rec_reqs.get("Storage", "")]
            csv_file.write(f'"{name}"')
            csv_file.write("," + f'"{release_date}"')
            csv_file.write("," + f'"{genre0}"')
            csv_file.write("," + f'"{genre1}"')
            csv_file.write("," + f'"{rating}"')
            for (index, req) in enumerate(reqs):
                csv_file.write("," + f'"{req}"')
            csv_file.write("\n")
        csv_file.flush()

    print(f"\nFinished after {time.time() - start_time} seconds\n")

# ----------------------------------------
def get_games(game_infos : dict, offset : int):
    link = f"https://store.steampowered.com/search/results/?query=&start={offset*50}&count=50&dynamic_data=&sort_by=_ASC&os=win&snr=1_7_7_7000_7&filter=topsellers&infinite=1"
    listPageRequest = requests.get(link)
    html = json.loads(listPageRequest.text)["results_html"]
    listPageSoup = bs(html, "lxml")
    gameRows = listPageSoup.find_all("a", {"class" : "search_result_row ds_collapse_flag"})
    for gameRow in gameRows:
        game_name_span = gameRow.find("span", {"class" : "title"})
        game_infos.append( 
            { "name" : game_name_span.string,
              "url"  : gameRow["href"] } 
        )
# ----------------------------------------
def get_more_data(game_info : dict):
    game_page_request = requests.get(game_info["url"])
    game_page_soup = bs(game_page_request.content, "lxml")

    get_release_date(game_info, game_page_soup)
    get_sys_reqs(game_info, game_page_soup)
    get_ratings(game_info, game_page_soup)
    get_genre(game_info, game_page_soup)

def get_sys_reqs(game_info : dict, game_page_soup : bs):
    sys_req_div = game_page_soup.find("div", {"class" : "game_area_sys_req sysreq_content active", "data-os" : "win"})
    min_col = sys_req_div.select_one(".game_area_sys_req_leftCol")
    rec_col = sys_req_div.select_one(".game_area_sys_req_rightCol")
    min_items = min_col.find_all("li")
    rec_items = rec_col.find_all("li")
    game_info["sys_reqs_min"] = {}
    game_info["sys_reqs_rec"] = {}
    for item in min_items:
        reqStrs = item.get_text().split(":")
        if (len(reqStrs) == 2):
            game_info["sys_reqs_min"][reqStrs[0].strip()] = reqStrs[1].strip()
    for item in rec_items:
        reqStrs = item.get_text().split(":")
        if (len(reqStrs) == 2):
            game_info["sys_reqs_rec"][reqStrs[0].strip()] = reqStrs[1].strip()

def get_release_date(game_info : dict, game_page_soup : bs):
    release_date_div = game_page_soup.select_one(".release_date .date")
    if release_date_div != None:
        game_info["release_date"] = release_date_div.string

def get_ratings(game_info : dict, game_page_soup : bs):
    ratings_meta = game_page_soup.find("meta", itemprop="ratingValue")
    if ratings_meta != None:
        game_info["rating"] = ratings_meta["content"]

def get_genre(game_info : dict, game_page_soup : bs):
    genres_and_manufacturer_div = game_page_soup.find("div", {"id" : "genresAndManufacturer"})
    if genres_and_manufacturer_div != None:
        genres_span = genres_and_manufacturer_div.find("span")
        first_genre_link = genres_span.find_next("a")
        if first_genre_link != None:
            game_info["genre0"] = first_genre_link.string
            second_genre_link = first_genre_link.findNextSibling("a")
            if second_genre_link != None:
                game_info["genre1"] = second_genre_link.string
# ----------------------------------------

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