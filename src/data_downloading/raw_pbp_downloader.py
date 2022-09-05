# -*- coding: utf-8 -*-
"""
Created on Fri Mar 18 21:50:28 2022

@author: Nicholas

Script for downloading a season's worth of PbP data
"""

#%% Imports
from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.library.parameters import SeasonTypeAllStar

from nba_api.stats.endpoints import playbyplayv2

import pathlib
import time
import pandas as pd
import sys
import argparse

#%%

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("dest", help="Destination folder")
parser.add_argument("season", help="Season String")
parser.add_argument("-a", "--api-delay", help="API delay", type=int, default=2)
parser.add_argument("-s", "--season-type", help="Season type, 0:regular, 1:playoffs, 2:preseason, 3:all star", 
                    type=int, default = 0)

args = parser.parse_args()


#%%

season_type_dic = {0: SeasonTypeAllStar.regular,
                   1: SeasonTypeAllStar.playoffs,
                   2: SeasonTypeAllStar.preseason,
                   3: SeasonTypeAllStar.all_star}

season_type = season_type_dic[args.season_type]



#%% CHANGE THIS!!!!!!

#season_string = "2019-20"
#season_type = SeasonTypeAllStar.default

#save_dir = pathlib.Path(r"C:\Users\Nicholas\Documents\NBA\data\raw_pbp_logs")

#api_delay = 2

#%% Helper functions

game_ids = leaguegamelog.LeagueGameLog(season=args.season, season_type_all_star=season_type).get_data_frames()[0]["GAME_ID"].unique()

#%%

# Creating all the necessary files and directories if necessary

output_dir = pathlib.Path(args.dest)
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir.joinpath(args.season+"_raw_PbP.csv")
finished_games_file = output_dir.joinpath(args.season+"_finished_games.csv")

if not finished_games_file.exists():
    game_id_df = pd.DataFrame(columns=["GAME_ID"])
    game_id_df.to_csv(finished_games_file, index=False)


i = 0
game_amount = game_ids.shape[0]

for game_id in game_ids:
    
    # Skipping games that have already been done
    finished_games = pd.read_csv(finished_games_file)["GAME_ID"].to_numpy()
    
    if game_id in finished_games:
        i += 1
        print("Already did game " + str(i) + " of " + str(game_amount))
        continue
    
    # Making the API call
    time.sleep(args.api_delay)
    curr_game_pbp = playbyplayv2.PlayByPlayV2(game_id).get_data_frames()[0]
    curr_game_pbp.drop_duplicates(inplace=True)
    
    # Saving the dat and the ID to the files
    if not output_file.exists():
        curr_game_pbp.to_csv(output_file, index=False)
    else:
        curr_game_pbp.to_csv(output_file, mode="a", index=False, header=False)
        
    game_id_df = pd.DataFrame({"GAME_ID":[game_id]})
    game_id_df.to_csv(finished_games_file, mode="a", index=False)
    
    i += 1
    print("Finished game " + str(i) + " of " + str(game_amount)) 
    
    


