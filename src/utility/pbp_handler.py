# -*- coding: utf-8 -*-
"""
Created on Fri Dec 24 13:25:42 2021

@author: Nicholas

Upgraded script for making sense of PBP information
"""

#%% Imports
import numpy as np
import pandas as pd
import math

pd.options.mode.chained_assignment = None


#%% General helper functions

def timestring_to_seconds(time_str):
    
    """
    Helper function for converting a minute:second string into a integer of
    seconds remaining
    """
    
    split_time = time_str.split(":")
    
    time_ = int(split_time[0])*60  + int(split_time[1])
    
    return time_


def seconds_to_timestring(sec_int):
    
    """
    Helper function that produces a game appropriate time string from an 
    integer amount of seconds.
    """
    
    mins = sec_int // 60
    sec = sec_int % 60
    
    output = str(mins) + ":" + str(sec).zfill(2)
    return output


def is_period_marking_timestamp(time_elapsed_int, ot_length_mins=5):
    
    """
    Function that when given the number f deciseconds elapsed in the game,
    returns true if that time starts/ends a period.
    
    This is useful when working with substitutions
    """
    
    # Handle regulation times
    if time_elapsed_int <= 4*12*60*10:
        return (time_elapsed_int % (12*60*10) == 0)
    
    # Now handle overtime
    else:
        ot_elapsed = time_elapsed_int - 4*12*60*10
        return (ot_elapsed % (ot_length_mins * 60*10) == 0)


def get_period_from_real_check_in_time(time_elapsed_int, ot_length_mins=5):
    
    """
    Given the exact (to the decisecond) check in time of a player, returns the 
    period that the player checked in in.
    """
    
    if time_elapsed_int < 12*60*4*10:
        
        period = time_elapsed_int // (12*60*10) + 1
        
    else:
        
        period = (time_elapsed_int - 12*60*4*10) // (ot_length_mins*60*10) + 5
    
    return period


def get_period_from_real_check_out_time(time_elapsed_int, ot_length_mins=5):
    
    """
    Given the exact (to the decisecond) check out time of a player, returns the 
    period that the player checked out in.
    """
    
    if time_elapsed_int < 12*60*4*10:
        
        period = time_elapsed_int // (12*60*10) 
        
    else:
        
        period = (time_elapsed_int - 12*60*4*10) // (ot_length_mins*60*10) + 4
    
    return period



def flatten(t):
    return [item for sublist in t for item in sublist]


def get_lineup_string(lineup):
    
    """
    Function that given either a list of players or an stringified list 
    (i.e. list that was saved to .csv by pandas, and ressembles a list being
     printed to the console), will return a uniformly formatted string. 
    """
    
    if type(lineup) == str:
        output = lineup.replace(" ", "")
        output = output.replace("[", "-")
        output = output.replace("]", "-")
        output = output.replace(',', "-")
        
        return output
    
    elif type(lineup) == list:
        
        joined_list = "-".join(lineup)
        output = "-" + joined_list + "-"
        
        return output


def squish_series(series):
    
    """
    When we have a series of repeated values, it is sometimes useful to know 
    where the switches happen, so for a long series a repeated values,
    only the first instance is preserved, as well as its index.
    
    Returns a series of alternating values.
    
    Ex: [A-A-A-B-B-B-A-A-A-C-C] -> [A-B-A-C]
    """
    indices_to_keep = []
    all_indices = series.index.tolist()
    
    indices_to_keep.append(all_indices[0])
    
    for i in range(1, len(all_indices)):
        
        prev_index = all_indices[i-1]
        curr_index = all_indices[i]
        
        if series[prev_index] != series[curr_index]:            
            indices_to_keep.append(curr_index)
    
    output = series[indices_to_keep]
    return output


def compare_series(s1, s2):
    
    """
    If both series are equal, returns true
    If not, returns indices where they differ
    """
    
    if (s1 != s2).sum() == 0:
        return True, None
    
    ineq_series = (s1 != s2)
    output = s1.index[ineq_series]
    
    return False, output


def zip_lists(l1, l2):
    
    """
    Zips two lists in alternating fashion
    """
    
    alternating_list = [None] * (len(l1) + len(l2))
    alternating_list[::2] = l1
    alternating_list[1::2] = l2
    
    return alternating_list
        

#%% Row processing helper functions

def get_elapsed_time(row):
    
    """
    Helper function that  given a row from a pbp dataframe, determines how much
    time has passed since the start of the game (in tenths of second)
    
    Assumes standard NBA rules (2021) of 12 minute quarters and 5 minute overtime
    periods.
    """
    
    period = row["PERIOD"]
    
    time_str = row["PCTIMESTRING"]
    time_comps = time_str.split(":")
    
    if period <= 4:
        quarter_elapsed_centiseconds = 12*60*10 - (int(time_comps[0])*60 + int(time_comps[1]))*10
    else:
        quarter_elapsed_centiseconds = 5*60*10 - (int(time_comps[0])*60 + int(time_comps[1]))*10
    
    if period <= 4:
        elapsed_periods_time = (period - 1) * 12 * 60 * 10
    else:
        elapsed_periods_time = (period-5)*5*60*10 + 48*60*10
    
    return quarter_elapsed_centiseconds + elapsed_periods_time


def is_time_off_inbound(row):
    
    """
    Sometimes, after a scored basket, the clock will be turned off. As of the 
    2021-2022 season, the rule is as follows:
        - Time is stopped if basket is scored in last minute of 1st, 2nd or 3rd 
        quarter
        - Time is stopped if basket is scored in last 2 minutes of 4th quarter
        or any overtime period
    
    This function returns true if the time should be turned off during the
    "live" inbound, or false if the time should be on.
    """
    
    period = row["PERIOD"]
    time_left = row["REMAINING_TIME"]
    
    if period < 4 and time_left <= 60:
        return True
    elif period >= 4 and time_left <= 120:
        return True
    else:
        return False


def clock_on(row):
    
    """
    Function that for given row, determines whether the clock is on or off.
    
    Important because for live events, there is a few second delay between
    the event taking place and the scorekeeper recording it.
    """
    
    event_code = row["EVENTMSGTYPE"]
    action_code = row["EVENTMSGACTIONTYPE"]
    action_details = row["ACTION_DETAILS"]
    
    # These event always result in stoppage of the clock
    if event_code in [3,6,7,8,9,11,12,13,18]:
        return False
    
    # Clock is always on for missed shots 
    # Jumpballs also behave as though the clock is on since all non-quarter 
    # opening tips are recorded when the ball is secured by a third player
    elif event_code in [2,10]:
        return True
    
    #Individual rebounds always have clock on
    elif event_code == 4 and action_details in ["OFFENSIVE", "DEFENSIVE"]:
        return True
    
    elif event_code == 4 and action_details in ["OFFENSIVE-TEAM", "DEFENSIVE-TEAM", "FAKE"]:
        return False
    
    # Live ball turnovers have clock on
    elif event_code in [5,0] and action_code in [1, 2]:
        return True
    
    # Dead ball turnovers always have clock off
    elif event_code in [5,0] and action_code not in [1, 2]:
        return False
    
    # AND1s stop the clock
    elif event_code == 1 and action_details in ["2PT-AND1", "3PT-AND1"]:
        return False
    
    # Non AND1s do not stop clock
    elif event_code == 1 and action_details in ["2PT", "3PT"]:
        return True
    
    # Inbounds based on whether they are in the appropriate game intervals
    elif event_code == 20 and action_code == 1:
        return True
    
    elif event_code == 20 and action_code == 2:
        return False
    
    else:
        print(event_code)
        raise Exception(event_code)
    
    
def estimate_actual_time_remaining(row, inbound_delay=2, keeper_delay=2, tip_adjustment=3):
    
    """
    Depending on the type, the recorded time stamp of an event can be different
    from its actual time stamp. THis helper function tries to estimate the 
    actual time remaining of an event.
    
    This functions has the quirk of having overtime periods and the first 
    quarter starting at an obviously impossible time, but this actuall makes
    the possessions a lot easier to work with.
    
    Also note that jump balls are super weird: if the tip is the opnening tip
    of a period, the timestamp is recorded at the period start (ex:12:00).
    If the jumpball is during play (because of two guys grabbing it), the 
    timestamp is recorded when the ball is collected by an external player.
    in the latter case we have the usual delay.
    """
    
    # Start of first quarter and OT
    if row["EVENTMSGTYPE"] == 12 and row["PERIOD"] not in [2,3,4]:
        return row["REMAINING_TIME"] - tip_adjustment
    
    # First quarter tip
    elif row["EVENTMSGTYPE"] == 10 and row["PCTIMESTRING"]=="12:00" and \
    row["PERIOD"]==1:
        return row["REMAINING_TIME"] - tip_adjustment
    
    # Overtime opening tips
    elif row["EVENTMSGTYPE"] == 10 and row["PCTIMESTRING"]=="5:00" and \
    row["PERIOD"]>4:
        return row["REMAINING_TIME"] - tip_adjustment
    
    elif not row["CLOCK_ON"]:
        return row["REMAINING_TIME"]
    
    elif row["EVENTMSGTYPE"] == 20:
        return row["REMAINING_TIME"] - inbound_delay
    
    else:
        return row["REMAINING_TIME"] + keeper_delay
    

def get_shotclock_value(row, unadjusted_shotclock, blocked=False):
    
    """
    Function that looks at a row an determines what the shotclock should be.
    
    unadjusted_shotclock is what the shotclock would be if we did not adjust 
    for the specific action in the row
    """
    
    event_code = row["EVENTMSGTYPE"]
    action_code = row["EVENTMSGACTIONTYPE"]
    details = row["ACTION_DETAILS"]
    
    # Offensive rebounds
    # Blocks normally don't allow the ball to touch the rim
    if event_code == 4 and details in ["OFFENSIVE", "OFFENSIVE-TEAM"] and not blocked:
        return 14
    
    
    # Non-special case fouls
    elif event_code == 6 and action_code in [1,2,6,28] and unadjusted_shotclock<14:
        return 14
    
    # Flagrants reset to 24
    elif event_code == 6 and action_code in [14,9,15,8]:
        return 24
    
    # Otherwise we don't reset the shotclock
    else:
        return unadjusted_shotclock
        
#%% Possession processing functions

def estimate_shotclock(poss_df, inbound_adjust=2, scorekeeper_delay=2, tip_adjustment=4):
    
    """
    Function for each event in the PbP estimates the shot clock at the time 
    of the event.
    
    inbound_adjust is a correction value since teams generally take a few 
    seconds to inbound the ball.
    
    scorekeeper_delay is a correction value for events that do no stop the
    game clock (ex :steal) to account for the time the scorekeeper took to
    actually input the event.
    
    tip_adjustment is the adjustment for the time between the tip being won 
    and the shot clock being started.
    
    Note that this script will erroneously reset the shotclock to 14 on 
    offensive rebounds following an airball. There is no good way to fix this
    
    Also note that the time to inound time is only approximate while the clock
    is on: for example, if the ball is rolled up the floor, there will be a 
    large error between the estimate and true value.
    """
    
    poss_copy = poss_df.copy()
    
    poss_copy["SHOTCLOCK"] = np.nan
    poss_copy["ACTUAL_REMAINING_TIME"] = poss_copy.apply(lambda row: estimate_actual_time_remaining(row), axis=1)
    
    start_row = poss_copy.iloc[0]
    
    prev_sc = 24
    prev_time = start_row["ACTUAL_REMAINING_TIME"]
    
    block_flag = False
    
    for i, row in poss_copy.iterrows():
        
        if (row["EVENTMSGTYPE"] == 2) and (row["PLAYER3_ID"] != 0):
            block_flag = True
            
            
        if i == poss_copy.index[0]:
            poss_copy.loc[i, "SHOTCLOCK"] = 24
        
        else:
            curr_time = row["ACTUAL_REMAINING_TIME"]
            
            elapsed_time = max(prev_time-curr_time, 0)

            unadjusted_sc = prev_sc - elapsed_time
            
            adjusted_sc = get_shotclock_value(row, unadjusted_sc, block_flag)
            
            poss_copy.loc[i, "SHOTCLOCK"] = adjusted_sc
            
            prev_sc = adjusted_sc
            prev_time = curr_time
        
        if (row["EVENTMSGTYPE"] == 4):
            block_flag = False
    
    return poss_copy


def approximate_set_defense(poss_df):
    
    """
    When there is a stoppage in play that appear in the PbP data, we know 
    for certain that the defense was given a chance to set themselves up.
    
    This function creates a new column on the possession dataframe, and determines
    whether the defense was set
    
    NOTE: when this variable is true, we are certain that the defense was set.
    When it is false, it means that in the PbP data, there was no way to 
    tell whether the defense was set
    
    Possessions are against unset defense if they begin with a defensive
    rebound or a steal, and there was no stoppages. (Jumpballs are 
    very rare and inconsistent, so they are ignored)
    
    Possessions can therefore start against unset defense, but after a 
    stoppage, the defense becomes set.
    """
    
    poss_df_copy = poss_df.copy()
    
    start_row = poss_df_copy.head(1).squeeze()
    
    stoppage_occured = False
    
    # If we have an inbound or a period start, the defense is set for the whole
    # possession
    
    if start_row["EVENTMSGTYPE"] in [12, 20]:
        
        poss_df_copy["SET_DEFENSE"] = True
        return poss_df_copy
    
    # we need to check for team defensive rebounds
    elif start_row["EVENTMSGTYPE"] == 4 and start_row["ACTION_DETAILS"] == "DEFENSIVE-TEAM":
        
        poss_df_copy["SET_DEFENSE"] = True
        return poss_df_copy
    
    # We need to check if the turnover was live
    elif start_row["EVENTMSGTYPE"] == 0 and start_row["PLAYER2_ID"] == 0:
        
        poss_df_copy["SET_DEFENSE"] = True
        return poss_df_copy
    
    poss_df_copy["SET_DEFENSE"] = False
    
    for i, row in poss_df_copy.iterrows():
        
        if row["CLOCK_ON"] and not stoppage_occured:
            
            continue
        
        elif not row["CLOCK_ON"]:
            poss_df_copy.loc[i, "SET_DEFENSE"] = True
            stoppage_occured = True
        
        else:
            poss_df_copy.loc[i, "SET_DEFENSE"] = True
    
    return poss_df_copy
    
  
# This one is technically not a possession df
# This function is a hot mess 
def order_putback_frenzy(df):
    
    """
    Input: jumbled df of shots ands offensive rebounds
    Output: ordered df of shots and rebounds
    """
    
    output_df_indices = df.index.tolist()
    output_df_indices.sort()
    
    # If all the indices arent consecutive numbers, we are probably missing important info,
    # and we should re-order
    if output_df_indices != list(range(min(output_df_indices), max(output_df_indices)+1)):
        
        return df
    
    
    score_dics = []
    shot_dics = []
    oreb_dics = []
    dreb_dics = []
    
    output_dics = []
    
    
    for i, row in df.iterrows():
        
        if row["EVENTMSGTYPE"] == 1:
            score_dics.append(row.to_dict())
            
        elif row["EVENTMSGTYPE"] == 2:
            shot_dics.append(row.to_dict())
            
        elif row["EVENTMSGTYPE"] == 4 and row["ACTION_DETAILS"] == "OFFENSIVE":
            oreb_dics.append(row.to_dict())
        
        elif row["EVENTMSGTYPE"] == 4 and row["ACTION_DETAILS"] == "DEFENSIVE":
            dreb_dics.append(row.to_dict())
            
    
    # If there are no rebounds of any kind, there is nothing to resolve
    if len(dreb_dics) + len(oreb_dics) == 0:
        return df
    
    
    if len(score_dics) > 1:
        return df
        
    if len(dreb_dics) > 1:
        raise Exception("Too many simultaneous defensive rebounds")
    
    
    # If there are no drebs or made shots, its really hard to tell what happened first
    if len(score_dics) + len(dreb_dics) == 0 and len(oreb_dics)==1 and len(shot_dics) == 1:
        df.sort_index(inplace=True)
        return df
    
        
    
    # Hardest case: both dreb and bucket
    if len(score_dics) == 1 and len(dreb_dics) == 1:
        
        # if teams are the same it was probably a very fast break
        # i.e. DREB then SCORE, but we reverse list at end
        if score_dics[0]["PLAYER1_TEAM_ID"] == dreb_dics[0]["PLAYER1_TEAM_ID"]:
            output_dics.append(score_dics[0])
            output_dics.append(dreb_dics[0])
            zipped_dics = zip_lists(shot_dics, oreb_dics)
            
            output_dics = output_dics + zipped_dics
            output_dics.reverse()
        
        # If teams are different, something really fucked happened 
        else:
            raise Exception("Simultaneous bucket and dreb by opposing teams", df["PCTIMESTRING"])
    
    # If there are are no scores and no drebs, the best we can do is have the
    # orebs aternate with the shots
    elif len(score_dics) + len(dreb_dics) == 0:
        if len(oreb_dics) >= len(shot_dics):
            output_dics = zip_lists(oreb_dics, shot_dics)
        else:
            output_dics = zip_lists(shot_dics, oreb_dics)
    
    # If there are no scores, the dreb comes after opposing shots
    # If the shooter is the same team as the rebounder, very fast beak, dreb comes first
    elif len(score_dics) == 0:
        
        output_dics.append(dreb_dics[0])
        zipped_dics = zip_lists(shot_dics, oreb_dics)
        
        output_dics = output_dics + zipped_dics
        output_dics.reverse()
        
        if len(shot_dics) == 1:
            if shot_dics[0]["PLAYER1_TEAM_ID"] == dreb_dics[0]["PLAYER1_TEAM_ID"]:
                output_dics.reverse()
        
        
    # If there are no drebs, score is last, event before is a oreb
    elif len(dreb_dics) == 0:
        output_dics.append(score_dics[0])
        zipped_dics = zip_lists(oreb_dics, shot_dics)
        
        output_dics = output_dics + zipped_dics
        output_dics.reverse()
    
        
    
    output_df = pd.DataFrame(output_dics)
    output_df.index = output_df_indices
    
    return output_df
    


    

#%% PBP data structure
class PBPHandler:
    
    def __init__(self, pbp_df):
        
        """
        Take as input a dataframe of PbP data that is or is not preprocessed 
        """
        
        self.raw_df = pbp_df.drop_duplicates().reset_index(drop=True)
        self.df = pbp_df.drop_duplicates().reset_index(drop=True)
        self.df["HOMEDESCRIPTION"].fillna(value="", inplace=True)
        self.df["VISITORDESCRIPTION"].fillna(value="", inplace=True)
        self.df["NEUTRALDESCRIPTION"].fillna(value="", inplace=True)
        
        if "ACTION_DETAILS" not in pbp_df.columns:
            self.df["ACTION_DETAILS"] = ""
        
        team_ids = self.df["PLAYER1_TEAM_ID"].unique()
        team_ids = team_ids[~np.isnan(team_ids)]
        
        self.inverter = {team_ids[0]:team_ids[1],
                         team_ids[1]:team_ids[0]}
        
        self.game_id = pbp_df["GAME_ID"].iloc[0]
        
        
    def _get_teams(self):
        
        """
        Returns a vector of length 2 of floats (and a warning if there aren't exactly 2 IDS)
        Home team is first away team is second
        """
        
        teams = self.df["PLAYER1_TEAM_ID"].unique()
        teams = teams[~np.isnan(teams)]
        
        if len(teams) != 2:
            raise Warning("Expected to return a vector of length 2, instead returned a vector of length " + str(teams.shape[0]))
        
        return teams.astype(int)
    
    
    def _get_readable_copy(self):
        
        """ 
        Returns a copy of self.df, but with a lot less columns 
        
        Drops a whole bunch of unreadable columns. Meant to facilitate testing
        """
        
        copy_df = self.df.drop(labels=["GAME_ID", "WCTIMESTRING", "PERSON1TYPE",\
                                "PLAYER1_TEAM_ID", "PLAYER1_TEAM_CITY", "PLAYER1_TEAM_NICKNAME", \
                                "PERSON2TYPE", "PLAYER2_ID", "PLAYER2_TEAM_ID", "PLAYER2_TEAM_CITY", \
                                "PLAYER2_TEAM_NICKNAME", "PERSON3TYPE", "PLAYER3_ID", "PLAYER3_TEAM_ID", \
                                "PLAYER3_TEAM_CITY", "PLAYER3_TEAM_NICKNAME", "VIDEO_AVAILABLE_FLAG"], axis=1)
        
        return copy_df
    
    
    def _assign_elapsed_time(self):
        
        """
        For each line, assign (game) time elapsed (in tenths of second) since starting tip. 
        
        Useful for ordering events and for getting time between events.
        """
        
        self.df["ELAPSED_TIME"] = self.df.apply(lambda row: get_elapsed_time(row), axis=1)
    
    

    
    def _assign_remaining_quarter_time(self):
        
        """
        Converts the time strings of quarter time remaining into integers
        of quarter time remaining (in seconds)
        """
        
        self.df["REMAINING_TIME"] = self.df["PCTIMESTRING"].apply(timestring_to_seconds)
        
    
    def _handle_simultaneous_rebs_TOs(self):
        
        """
        If we have a smilutaneous rebound and TO, we order by the eventnum
        """
        to_df = self.df.loc[self.df["EVENTMSGTYPE"]==5]
        to_timestamps = to_df["ELAPSED_TIME"].unique()
        
        for t in to_timestamps:
            
            simultaneous_reb_to_df  = self.df.loc[(self.df["ELAPSED_TIME"]==t) & (self.df["EVENTMSGTYPE"].isin([4,5]))]
            
            if simultaneous_reb_to_df.shape[0] == 2:
                
                # If the gap in event numbers is really large, we can assume
                # that this was a manual correction and was accurate
                #if abs(simultaneous_reb_to_df["EVENTNUM"].iloc[0]-simultaneous_reb_to_df["EVENTNUM"].iloc[1]) > 5:
                    #continue
                
                # If the events are not next to each other, we dont touch them
                if abs(simultaneous_reb_to_df.index[0]-simultaneous_reb_to_df.index[1]) > 1:
                    continue                                                           
                
                # Sorting by event code makes the rebound come first
                reordered_df = simultaneous_reb_to_df.sort_values(by="EVENTMSGTYPE")
                
                reordered_indices = list(reordered_df.index)
                reordered_indices.sort()
                
                reordered_df.index = reordered_indices
                
                self.df.loc[reordered_indices, :] = reordered_df
                
                
    
    
    def _order_pbp(self):
        
        """        
        When there is a long series of simultaneous shots and offensive rebounds,
        the API sometime returns them out of order.
        
        This function re-orders these isntances. There is no guarantee that all
        the rebounds and shots are exaclt in the right order: all that is guaranteed
        is that the made basket will be at the end and shots and rebounds will
        alternate (for example, two rebounds may be swapped with each other)
        """
        
        shot_df = self.df.loc[self.df["EVENTMSGTYPE"].isin([1,2]) & ~(self.df["ACTION_DETAILS"].str.contains("AND1"))]
        
        shot_times = shot_df["ELAPSED_TIME"].unique()
        
        
        for time in shot_times:
            
            curr_score_df = self.df.loc[(self.df["ELAPSED_TIME"]==time) & (self.df["EVENTMSGTYPE"]==1)]
                
                
            curr_shot_df = self.df.loc[(self.df["ELAPSED_TIME"]==time) & (self.df["EVENTMSGTYPE"]==2)]
            
            curr_oreb_df = self.df.loc[(self.df["ELAPSED_TIME"]==time) & (self.df["EVENTMSGTYPE"] == 4) &
                                 (self.df["ACTION_DETAILS"]=="OFFENSIVE")]
            
            curr_dreb_df = self.df.loc[(self.df["ELAPSED_TIME"]==time) & (self.df["EVENTMSGTYPE"] == 4) &
                                 (self.df["ACTION_DETAILS"]=="DEFENSIVE")]
            
            # THIS IS WHERE WE START BLASTING
            
            curr_sub_df = pd.concat([curr_shot_df, curr_oreb_df, curr_score_df, curr_dreb_df], axis=0)

            
            # If the shape is <= 1 then all that happened was the shot
            if curr_sub_df.shape[0] > 1:
                re_ordered = order_putback_frenzy(curr_sub_df)
                
                self.df.loc[re_ordered.index, :] = re_ordered
            
            

    
    
    def _ft_results(self):
        
        """
        The only distinction from made and missed free throws comes from the 
        description. 
        
        This function stores the difference in the ACTION_DETAILS column
        """
        
        def temp(desc):
            
            if len(desc) == 0:
                return ""
            
            elif "MISS" in desc:
                return "MISSED"
            else:
                return "MADE"
        
        ft_df = self.df.loc[self.df["EVENTMSGTYPE"]==3] 
        
        ft_res1 = ft_df["HOMEDESCRIPTION"].apply(temp).tolist()
        ft_res2 = ft_df["VISITORDESCRIPTION"].apply(temp).tolist()
        
        full_res = [a+b for a,b in zip(ft_res1, ft_res2)]
        
        self.df.loc[ft_df.index, "ACTION_DETAILS"] = full_res
    
    
    def _shot_type(self):
        
        """
        There is no code difference between 3 point shots and 2 point shots,
        the only diffrence is in the description.
        
        This functions stores the difference in the ACTION_DETAILS column
        """
        
        def temp(desc):
            
            if (len(desc)==0) or ("BLOCK" in desc):
                return ""
            elif "3PT" in desc:
                return "3PT"
            else:
                return "2PT"
        
        shot_df = self.df.loc[self.df["EVENTMSGTYPE"].isin([1,2])]
        
        shot_type1 = shot_df["HOMEDESCRIPTION"].apply(temp).tolist()
        shot_type2 = shot_df["VISITORDESCRIPTION"].apply(temp).tolist()
        
        full_types = [a+b for a,b in zip(shot_type1, shot_type2)]
        
        self.df.loc[shot_df.index, "ACTION_DETAILS"] = full_types
    
    
    def _rebound_type(self):
        
        """
        There is no code difference between offensive rebounds and defensive
        rebounds. There is no difference in the description either, the only
        way to know what type of rebound is by seeing which team missed the
        shot that led to the rebound.
        
        Also, for some reason the NBA allocates team rebounds after a missed
        non-final free throw. These are re-labeled as "FAKE". These rebounds 
        have an EVENTMSGACTIONTYPE value of 1.
        
        We also distinguish between team and individual rebounds.
        """
        
        true_rebs_df = self.df.loc[(self.df["EVENTMSGTYPE"]==4) & 
                                         (self.df["EVENTMSGACTIONTYPE"]==0)]
        
        rebound_types = []
        
        
        for i, row in true_rebs_df.iterrows():
            
            # First determine which team has the ball (tricky because team
            # rebounds store this in different place than individual rebounds)
            rebounding_team_id = None
            
            # If the value is a float, we know there was no name
            if type(row['PLAYER1_NAME']) != str:
                rebounding_team_id = row["PLAYER1_ID"]
            else:
                rebounding_team_id = row["PLAYER1_TEAM_ID"]
        
            # Now go find the last miss
            
            for j in range(i-1,0,-1):
                
                curr_action_code = self.df.loc[j, "EVENTMSGTYPE"]
                
                # Missed FG
                if curr_action_code == 2:
                    
                    shooting_team_id = self.df.loc[j,"PLAYER1_TEAM_ID"]
                    
                    if shooting_team_id == rebounding_team_id:
                        rebound_types.append("OFFENSIVE")
                    else:
                        rebound_types.append("DEFENSIVE")
                    
                    break
                    
                # Missed FT
                if curr_action_code == 3 and self.df.loc[j, "ACTION_DETAILS"] == "MISSED":
                    
                    shooting_team_id = self.df.loc[j,"PLAYER1_TEAM_ID"]
                    
                    if shooting_team_id == rebounding_team_id:
                        rebound_types.append("OFFENSIVE")
                    else:
                        rebound_types.append("DEFENSIVE")
                    
                    break
                
                else:
                    continue
            
        self.df.loc[true_rebs_df.index, "ACTION_DETAILS"] = rebound_types
        
        # Now handle fake rebounds
        
        self.df.loc[(self.df["EVENTMSGTYPE"]==4) & \
                    (self.df["EVENTMSGACTIONTYPE"]==1), "ACTION_DETAILS"] = "FAKE"
             
        # Now adapt for team rebounds
        team_rebound_indices = true_rebs_df.index[true_rebs_df["PLAYER1_NAME"].isnull()]
        new_rebound_details = self.df.loc[team_rebound_indices, "ACTION_DETAILS"].copy() + "-TEAM"
        
        self.df.loc[team_rebound_indices, "ACTION_DETAILS"] = new_rebound_details
        
    
    def _add_and1s(self):
        
        """
        Function that edits the ACTION_DETAILS to distinguish and1s from 
        non-and1s.
        
        This is in important distinction because and1s do not end possessions.   
        
        And1s do not have a special code to distinguish them from away from 
        play fouls, so we simply check if a shot took place in the same second.
        
        This function also changes the EVENTMSGACTIONTYPE value of away from play
        fouls (2021 season definition) to 100.
        """
        
        and1_ft_df = self.df.loc[(self.df["EVENTMSGTYPE"]==3) & (self.df["EVENTMSGACTIONTYPE"]==10)]
        
        for i, row in and1_ft_df.iterrows():
            
            ft_shooting_team = row["PLAYER1_TEAM_ID"]
            
            elapsed_time = row["ELAPSED_TIME"]
            
            simultaneous_actions_df = self.df.loc[self.df["ELAPSED_TIME"]==elapsed_time].loc[:i-1]
            
            # Reverse the order to find the most "recent" shot
            for j in reversed(simultaneous_actions_df.index):
                
                away_from_play = True
                if self.df.loc[j, "EVENTMSGTYPE"] == 1 and self.df.loc[j, "PLAYER1_TEAM_ID"]==ft_shooting_team and \
                    "AND1" not in self.df.loc[j, "ACTION_DETAILS"]:
                    
                    self.df.loc[j, "ACTION_DETAILS"] = self.df.loc[j, "ACTION_DETAILS"] + "-AND1"
                    away_from_play = False
                    break
                
            if away_from_play:
                self.df.loc[i, "EVENTMSGACTIONTYPE"] = 100
    
    
    def _add_and1s2(self):
        
        scores_df = self.df.loc[self.df["EVENTMSGTYPE"] == 1]
        
        # Looping through FGs to find the AND1s
        for i, row in scores_df.iterrows():
            
            shooter_team = row["PLAYER1_TEAM_ID"]
            
            shot_timestamp = row["ELAPSED_TIME"]
            
            simultaneous_df = self.df.loc[self.df["ELAPSED_TIME"]==shot_timestamp]
            
            # The foul needs to come after the shpt
            shooting_foul_df = simultaneous_df.loc[(simultaneous_df["EVENTMSGTYPE"]==6) & \
                                                   (simultaneous_df["EVENTMSGACTIONTYPE"].isin([1,2, 14])) & \
                                                       (simultaneous_df["PLAYER1_TEAM_ID"]!=shooter_team)].loc[i:,:]
                
            if shooting_foul_df.shape[0] > 0:
                self.df.loc[i, "ACTION_DETAILS"] = self.df.loc[i, "ACTION_DETAILS"] + "-AND1"
        
        
        # Now we need to find the FTs that are away from play
        
        single_ft = self.df.loc[(self.df["EVENTMSGTYPE"]==3) & (self.df["EVENTMSGACTIONTYPE"]==10)]
        
        for i, row in single_ft.iterrows():
            
            ft_timestamp = row["ELAPSED_TIME"]
            
            simultaneous_df = self.df.loc[self.df["ELAPSED_TIME"]==ft_timestamp]
            
            simultaneous_and1_df = simultaneous_df.loc[simultaneous_df["ACTION_DETAILS"].str.contains("AND1")]
            
            if simultaneous_and1_df.shape[0] == 0:
                self.df.loc[i, "EVENTMSGACTIONTYPE"] = 100

            
    def _adjust_putback_time(self, reb_delay=2, putback_delay=1):
        
        """
        Adjusts the timestamp of putback tips and dunks.
        
        On putbacks, the scorekeeper is generally very late to record the
        attemp (> 5 seconds). We fix this by assuming the offensive rebound 
        comes reb_delay seconds after the missed shot, and the putback attempt 
        comes putback_delay seconds after the rebound.
        """
        
        putback_codes= [72, 97, 87, 107]
        
        putback_df = self.df.loc[(self.df["EVENTMSGTYPE"].isin([1,2])) & (self.df["EVENTMSGACTIONTYPE"].isin(putback_codes))]
        
        for i, row in putback_df.iterrows():
            
            # If we have an AND1, the timestamp is exact
            if row["ACTION_DETAILS"] in ["2PT-AND1", "3PT-AND1"]:
                continue
            
            # If the action before is not an offensive rebound, skip
            if not (self.df.loc[i-1, "EVENTMSGTYPE"]==4 and self.df.loc[i-1, "ACTION_DETAILS"]=="OFFENSIVE"):
                continue
            
            for j in range(i-1, 0, -1):
                
                # Find the shot being rebounded
                if self.df.loc[j, "EVENTMSGTYPE"] in [2,3]:
                    break
            
            # Offensive reobunds of FTs are not prone to this delay problem 
            # since play is dead before the rebound
            if self.df.loc[j, "EVENTMSGTYPE"] == 3:
                continue
            
            shot_rebound_delay = self.df.loc[j, "REMAINING_TIME"] - self.df.loc[i-1, "REMAINING_TIME"]
            
            if shot_rebound_delay > 2:
                
                # Adjust all the values
                new_reb_time_remaining = self.df.loc[j, "REMAINING_TIME"] - reb_delay
                new_reb_time_elapsed = self.df.loc[j, "ELAPSED_TIME"] + 10*reb_delay
                new_reb_time_str = seconds_to_timestring(new_reb_time_remaining)
                
                new_shot_time_remaining = new_reb_time_remaining - putback_delay
                new_shot_time_elapsed = new_reb_time_elapsed + 10*putback_delay
                new_shot_time_str = seconds_to_timestring(new_shot_time_remaining)
                
                # Put them back into the dataframe
                self.df.loc[i-1, "PCTIMESTRING"] = new_reb_time_str
                self.df.loc[i-1, "ELAPSED_TIME"] =  new_reb_time_elapsed
                self.df.loc[i-1, "REMAINING_TIME"] = new_reb_time_remaining
                
                self.df.loc[i, "PCTIMESTRING"] = new_shot_time_str
                self.df.loc[i, "ELAPSED_TIME"] =  new_shot_time_elapsed
                self.df.loc[i, "REMAINING_TIME"] = new_shot_time_remaining

                
    def _add_inbounds(self):
        
        """
        Function that add live inbounds after made field goals and free throws.
        
        EVENTMSGTYPE of any inbound is 20
        
        EVENTMSGACTIONTYPE of 1 means the clock is on.
        EVENTMSGACTIONTYPE of 2 means the clock is off.
        """
        
        made_shot_df = self.df.loc[(self.df["EVENTMSGTYPE"]==1) & 
                                   ((self.df["ACTION_DETAILS"]=="2PT") | 
                                    (self.df["ACTION_DETAILS"]=="3PT"))]
        
        
        for i, shot_row in made_shot_df.iterrows():
            
            time_off = is_time_off_inbound(shot_row)
            
            inbound_row = shot_row.copy()
            inbound_row["EVENTNUM"] = shot_row["EVENTNUM"]
            inbound_row["EVENTMSGTYPE"] = 20
            inbound_row["EVENTMSGACTIONTYPE"] = time_off+1
            inbound_row["HOMEDESCRIPTION"] = ""
            inbound_row["NEUTRALDESCRIPTION"] = "LIVE INBOUND"
            inbound_row["VISITORDESCRIPTION"] = ""
            inbound_row["PERSON1TYPE"] = -1
            inbound_row["PLAYER1_ID"] = self.inverter[shot_row["PLAYER1_TEAM_ID"]]
            inbound_row["PLAYER1_NAME"] = None
            inbound_row["PLAYER1_TEAM_ID"] = np.nan
            inbound_row["PLAYER1_TEAM_CITY"] = None
            inbound_row["PLAYER1_TEAM_NICKNAME"] = None
            inbound_row["PLAYER1_TEAM_ABBREVIATION"] = None
            inbound_row["PERSON2TYPE"] = -1
            inbound_row["PLAYER2_ID"] = 0
            inbound_row["PLAYER2_NAME"] = None
            inbound_row["PLAYER2_TEAM_ID"] = np.nan
            inbound_row["PLAYER2_TEAM_CITY"] = None
            inbound_row["PLAYER2_TEAM_NICKNAME"] = None
            inbound_row["PLAYER2_TEAM_ABBREVIATION"] = None
            inbound_row["ACTION_DETAILS"] = ""
            
            self.df.loc[i+0.5] = inbound_row
            
            
        
        self.df.sort_index(inplace=True)
        self.df.reset_index(drop=True, inplace=True)
        
        made_final_ft_df = self.df.loc[(self.df["EVENTMSGTYPE"]==3) & 
                                       (self.df["EVENTMSGACTIONTYPE"].isin([10, 12, 15])) &
                                       (self.df["ACTION_DETAILS"]=="MADE")]
        
        for i, ft_row in made_final_ft_df.iterrows():
            
            inbound_row = ft_row.copy()
            inbound_row["EVENTNUM"] = ft_row["EVENTNUM"]
            inbound_row["EVENTMSGTYPE"] = 20
            inbound_row["EVENTMSGACTIONTYPE"] = 2
            inbound_row["HOMEDESCRIPTION"] = ""
            inbound_row["NEUTRALDESCRIPTION"] = "LIVE INBOUND"
            inbound_row["VISITORDESCRIPTION"] = ""
            inbound_row["PERSON1TYPE"] = -1
            inbound_row["PLAYER1_ID"] = self.inverter[ft_row["PLAYER1_TEAM_ID"]]
            inbound_row["PLAYER1_NAME"] = None
            inbound_row["PLAYER1_TEAM_ID"] = np.nan
            inbound_row["PLAYER1_TEAM_CITY"] = None
            inbound_row["PLAYER1_TEAM_NICKNAME"] = None
            inbound_row["PLAYER1_TEAM_ABBREVIATION"] = None
            inbound_row["PERSON2TYPE"] = -1
            inbound_row["PLAYER2_ID"] = 0
            inbound_row["PLAYER2_NAME"] = None
            inbound_row["PLAYER2_TEAM_ID"] = np.nan
            inbound_row["PLAYER2_TEAM_CITY"] = None
            inbound_row["PLAYER2_TEAM_NICKNAME"] = None
            inbound_row["PLAYER2_TEAM_ABBREVIATION"] = None
            inbound_row["ACTION_DETAILS"] = ""
            
            self.df.loc[i+0.5] = inbound_row
        
        self.df.sort_index(inplace=True)
        self.df.reset_index(drop=True, inplace=True)
    
    
    def _propogate_margin(self):
        
        """
        Function that propagates the score margin and current score string.
        
        Raw dataframes simply note changes when they occur and leave the cell 
        empty for events that don't it. 
        
        Also converts margin from a string to an integer.
        """
        
        margin = self.df["SCOREMARGIN"].replace(to_replace={"TIE":"0"})
        
        margin[0] = "0"
        margin.ffill(inplace=True)
        int_margin = margin.astype(int)
        
        self.df["SCOREMARGIN"] = int_margin
        
        score_col = self.df["SCORE"].copy()
        score_col[0] = "0 - 0"
        score_col.ffill(inplace=True)
        self.df["SCORE"] = score_col
    
    
    def _identify_TO_team(self):
        
        """
        The team id for team turnovers is not stored in the same place as
        for player turnovers.
        
        This function just copies it into PLAYER1_TEAM_ID 
        """
        
        to_df = self.df.loc[self.df["EVENTMSGTYPE"]==5]
        
        team_to_codes = [9,10,11]
        
        for i, row in to_df.iterrows():
            
            # 5 second violations are called for both teams and players
            # so we need to check if the player 1 team Id is null
            if row["EVENTMSGACTIONTYPE"] in team_to_codes and np.isnan(row["PLAYER1_TEAM_ID"]):
            
                self.df.loc[i, "PLAYER1_TEAM_ID"] = row["PLAYER1_ID"]              
    

    def _find_flagrant_to(self):
        
        """
        Sometimes, a flagrant that for all intents and purposes is a turnover 
        is not recorded as such (ex: flagrant after made basket)
        
        This is very rare, but messes up the parsing for the rest of the
        possession, so this function corrects it by adding into to the 
        ACTION_DETAILS column
        """
        
        # Check if start of possession team is same as flagrant foul team
        # Start at flagrant, loop up until an identifying event is found
        
        #drebs, forced TOs, inbounds, jumpballs, starts of periods always begin possessions
        
        flagrant_df = self.df.loc[(self.df["EVENTMSGTYPE"]==6) & (self.df["EVENTMSGACTIONTYPE"]==14)]

        
        # For each flagrant, see who had the ball before the flagrant
        for i, row in flagrant_df.iterrows():
            
            # Sometimes the flagrant is correctly followed by a turnover
            # So we need to skip these cases
            
            flagrant_time = row["ELAPSED_TIME"]
            flag_committer = row["PLAYER1_ID"]
            
            present_flag_to = self.df.loc[(self.df["ELAPSED_TIME"]==flagrant_time) & \
                                          (self.df["EVENTMSGTYPE"]==5) & \
                                              (self.df["PLAYER1_ID"]==flag_committer)]
            
            if present_flag_to.shape[0] > 0:
                continue
            
            for j in range(i-1, -1, -1):
                
                curr_code = self.df.loc[j,"EVENTMSGTYPE"]
                
                # If previoous discernible event was an inbound
                if curr_code == 20:
                    
                    curr_team_id = self.df.loc[j,"PLAYER1_ID"]
                
                # If previous discernible event was a forced turrnover
                elif curr_code == 5:
                    
                    curr_team_id = self.inverter[self.df.loc[j, "PLAYER1_TEAM_ID"]]
                
                # If previous discernible event was a team defensive rebound
                elif curr_code == 4 and self.df.loc[j,"ACTION_DETAILS"] == "DEFENSIVE-TEAM":
                    curr_team_id = self.df.loc[j,"PLAYER1_ID"]
                
                # if pervious discernible event was an individual defensive rebound
                elif curr_code == 4 and self.df.loc[j,"ACTION_DETAILS"] == "DEFENSIVE":
                    curr_team_id = self.df.loc[j,"PLAYER1_TEAM_ID"]
                
                # jumpballs
                elif curr_code == 10:
                    curr_team_id = int(self.df.loc[j,"ACTION_DETAILS"])
                
                # All other events are irrelevant
                else:
                    continue
            

            if curr_team_id  == row["PLAYER1_TEAM_ID"]:
                
                self.df.loc[i, "ACTION_DETAILS"] = "TO"
                break


    def _double_turnovers(self):
        
        """
        Function that doubles each turnover and changes the EVENTMSGTYPE code
        of the second duplicated turnover to 0.
        
        The reason for this is that when handling individual possessions, when
        a turnover occurs, it is hard to say who exactly has the ball during
        the turnover, and makes looking at individual possessions confusing.
        """
        
        to_df = self.df.loc[(self.df["EVENTMSGTYPE"]==5) | ((self.df["EVENTMSGTYPE"]==6)&(self.df["ACTION_DETAILS"]=="TO"))].copy()
        
        to_df["EVENTMSGTYPE"] = 0
        
        to_df.index = to_df.index + 0.5
        
        self.df = pd.concat([self.df, to_df])
        
        self.df.sort_index(inplace=True)
        self.df.reset_index(drop=True, inplace=True)
    
    
    def _notify_excess_timeout_technicals(self):
        
        """
        Excess timeout technicals are very difficult to handle because they
        have very little identifying information (no team nor player is
        assigned the technical), and generally there is a lot of confusion
        by the scorekeepers and referees if one is called. They are also 
        incredibly rare. So if one is detected, we simply throw an exception.
        """
        
        excess_timeout_df = self.df.loc[(self.df["EVENTMSGTYPE"]==5) & (self.df["EVENTMSGACTIONTYPE"]==42)]
        
        
        if excess_timeout_df.shape[0] > 0:
            
            game_id = self.df["GAME_ID"].to_numpy()[0]
            
            raise ValueError("Excess timeout technical was found in game: " + game_id)
    
    
    def _get_jumpball_winner(self):
        
        """
        Two things can happen on a jump ball:
            - Jumper tips ball to a teammate -> Player 3 data is filled out as per usual
            - One of the jumper tips the ball out of bounds -> Player 3 data is filled out
            with team data in a very wonky fasion
            
        This function updates the ACTION_DETAILS value of jump balls tothe ID
        of the tean that won the tip in both cases.
        
        Function also replaces jumpball violations with the same EVENTMSGTYPE
        as jumpballs, but with a custome EVENTMSGACTIONTYPE (20)
        
        """
        
        jumpball_df = self.df.loc[self.df["EVENTMSGTYPE"]==10]
        
        for i, row in jumpball_df.iterrows():
            
            if (pd.isna(row["PLAYER3_NAME"])):
                self.df.loc[i, "ACTION_DETAILS"] = str(int(row["PLAYER3_ID"]))
            else:
                self.df.loc[i, "ACTION_DETAILS"] = str(int(row["PLAYER3_TEAM_ID"]))
        
        jumpball_violation_df = self.df.loc[(self.df["EVENTMSGTYPE"]==7) & (self.df["EVENTMSGACTIONTYPE"]==4)]
        
        for i, row in jumpball_violation_df.iterrows():
            
            self.df.loc[i,"EVENTMSGTYPE"] = 10
            self.df.loc[i, "EVENTMSGACTIONTYPE"] = 20
            self.df.loc[i, "ACTION_DETAILS"] = self.inverter[row["PLAYER1_TEAM_ID"]]
        
    

    def _assign_possession(self):
        
        """
        Function that for every line in the dataframe, assigns possession.
        
        Also numbers the possessions
        
        """
        
        
        self.df["POSS"] = np.nan
        self.df["POSS_ID"] = np.nan
        
        # A possession is started by an inbound, an opponent TO, a defensive 
        # rebound, the start of a quarter or a won jump ball
        
        # First we handle defensive rebounds
        drebs_df = self.df.loc[(self.df["EVENTMSGTYPE"]==4) & 
                               (self.df["ACTION_DETAILS"].isin(["DEFENSIVE", "DEFENSIVE-TEAM"]))]
                
        rebound_actions_poss = drebs_df["PLAYER1_TEAM_ID"]
        
        team_reb_indices = rebound_actions_poss.isnull()
        
        rebound_actions_poss.loc[team_reb_indices] = drebs_df["PLAYER1_ID"].loc[team_reb_indices]
        self.df.loc[drebs_df.index, "POSS"] = rebound_actions_poss
        
        # Now we do inbounds 
        inbound_col = self.df.loc[self.df["EVENTMSGTYPE"]==20]["PLAYER1_ID"]
        self.df.loc[inbound_col.index, "POSS"] = inbound_col
        
        # Now opponent turnovers
        to_df = self.df.loc[self.df["EVENTMSGTYPE"]==0]
        
        to_inversed_poss = to_df["PLAYER1_TEAM_ID"]
        team_to_indices = to_inversed_poss.isnull()
        
        
        to_inversed_poss.loc[team_to_indices] = to_df["PLAYER1_ID"].loc[team_to_indices]
        
        
        to_poss = to_inversed_poss.apply(lambda x: self.inverter[x])
        
        self.df.loc[to_df.index, "POSS"] = to_poss
        
        # Now do jump balls
        # Remember that action details contains the id of the tip winner
        jump_ball_df = self.df.loc[self.df["EVENTMSGTYPE"]==10]
        
        for i, row in jump_ball_df.iterrows():
            
            # If the jumpball is due to players getting wrapped, the players will be given a steal and turnover
            # appropriately, so ignore these by checking if the tip is followed by a steal by the tip winner
            if self.df.loc[i+1, "EVENTMSGTYPE"] == 5 and \
                self.df.loc[i+1, "PLAYER1_TEAM_ID"]==self.inverter[int(row["ACTION_DETAILS"])]:
                continue
            
            self.df.loc[i, "POSS"] = int(row["ACTION_DETAILS"])
                
        
        # Now fill the possession data between
        periods = self.df["PERIOD"].unique()
        

        
        for period in periods:
            period_poss = self.df.loc[self.df["PERIOD"]==period]["POSS"]
            
            second_poss_id = period_poss[~period_poss.isnull()].to_numpy()[0]
            
            # If the second posession was initiated by a tip, we cant use
            # the sneaky inversion trick
            second_poss_start_index = period_poss[~period_poss.isnull()].index[0]
            if self.df.loc[second_poss_start_index, "EVENTMSGTYPE"] == 10:
                second_poss_initiated_jumpball = True
            else:
                second_poss_initiated_jumpball = False
            
            
            # If the period starts with a tip it has been handled by the jumpball logic
            if period in [2,3,4]:
                if not second_poss_initiated_jumpball:
                    self.df.loc[period_poss.index[0], "POSS"] = self.inverter[second_poss_id]
                    
                # We need to rely on possession rules    
                else:
                    jump_ball_winner = self.df["POSS"][~self.df["POSS"].isnull()].to_numpy()[0] 
                    
                    temp_dic ={2:self.inverter[jump_ball_winner],
                               3:self.inverter[jump_ball_winner],
                               4:jump_ball_winner}
                    
                    self.df.loc[period_poss.index[0], "POSS"] = temp_dic[period]
                    
            else:
                self.df.loc[period_poss.index[0], "POSS"] = second_poss_id
            
            
            new_period_poss = self.df.loc[self.df["PERIOD"]==period]["POSS"]
            filled_poss = new_period_poss.ffill()
            self.df.loc[new_period_poss.index, "POSS"] = filled_poss
        
        # Now we assign the possession id
        cum_poss = 0
        for p in periods:
            
            period_df = self.df.loc[self.df["PERIOD"]==p]
            
            poss_switch_indices = squish_series(period_df["POSS"])
            poss_id_vec = np.arange(1, poss_switch_indices.shape[0]+1) + cum_poss
            
            self.df.loc[poss_switch_indices.index, "POSS_ID"] = poss_id_vec
            
            cum_poss = poss_id_vec[-1]
            
        filled_poss_id = self.df["POSS_ID"].ffill()
        self.df["POSS_ID"] = filled_poss_id


    def _assign_defense(self):
        
        """
        Function creates a new column that is the opposite of the team with
        possession (i.e. the defending team)
        """
        
        self.df["DEFENSE"] = self.df["POSS"].apply(lambda x: self.inverter[x])
    
    
    def _assign_clock_on(self):
        
        """
        Function that assigns a boolean value to each row, true if the clock is
        running during the action, false if the clock is off
        """
        
        self.df["CLOCK_ON"] = self.df.apply(lambda row: clock_on(row), axis=1)
    
    
    def _assign_chance_number(self):
        """
        Slices the posession based on the current "attempt" of the posession (an new attempt starts
        after an offensive rebound)
        """
        self.df["OPPORTUNITY_NUM"] = np.empty(self.df.shape[0])
        
        poss_nums = self.df["POSS_ID"].unique()
        
        for poss in poss_nums:
            
            # Selecting the relevant sub-dataframe
            poss_sub_df = self.df[self.df["POSS_ID"]==poss]
            
            # Getting the number of opportunities on the posession
            #opportunities = (poss_sub_df["ACTION_TYPE"] == "OFFENSIVE REBOUND").sum() + 1
            opportunities = (poss_sub_df.loc[(poss_sub_df["EVENTMSGTYPE"]==4)&(poss_sub_df["ACTION_DETAILS"]=="OFFENSIVE")]).shape[0] + 1
            if opportunities == 1:
                self.df.loc[poss_sub_df.index, "OPPORTUNITY_NUM"] = 1
            else:
                off_rebounds_index = list((poss_sub_df.loc[(poss_sub_df["EVENTMSGTYPE"]==4)&(poss_sub_df["ACTION_DETAILS"]=="OFFENSIVE")]).index)
                opp_indices = [list(poss_sub_df.index)[0]] + off_rebounds_index + [list(poss_sub_df.index)[-1]]
                
                opp_num = 1
                for i in range(len(opp_indices)-1):
                    curr_opp_indices = np.arange(opp_indices[i], opp_indices[i+1]+1)
                    self.df.loc[curr_opp_indices, "OPPORTUNITY_NUM"] = opp_num
                    opp_num += 1
        
        
        self.df.loc[self.df["POSS_ID"].isnull(),"OPPORTUNITY_NUM"] = 0
        
    
    def _process_possessions(self, fct_list):
        
        """
        Some functions involve splitting the game into possessions, and then
        handling those possessions individually, before resticthing everything 
        back up again.
        
        This function is a hub to call all the possession based functions in a
        single place, so that we only need to do one splitting and re-zipping
        of the dataframe
        """
    
        raw_poss_df_list = [v for k,v in self.df.groupby("POSS_ID")]
        
        processed_df_list = []
        
        # This is where are all the actual processing functioins get called
        for poss_df in raw_poss_df_list:
            
            curr_poss_state = poss_df.copy()
            
            for fct in fct_list:
                
                curr_poss_state = fct(curr_poss_state)
            
            processed_df_list.append(curr_poss_state)
        
        rezipped_df = pd.concat(processed_df_list)
        
        self.df = rezipped_df
            
      
    def _verify_parsing(self):
        
        """
        Function that roughly checks if the parsing has been done correctly
        by doing a very rough sanity check (ex: only team with possession can
        shoot the ball)
        """
        
        # Make sure we didnt lose any events
        raw_events = np.sort(self.raw_df["EVENTNUM"].unique())
        proc_events = np.sort(self.df["EVENTNUM"].unique())
        
        if np.sum(raw_events != proc_events) != 0:
            raise Exception(self.game_id, "Lost events")
        
        # Offensive teams can shoot the ball or FTs,
        # Offensive team can collect offensive rebounds
        # Offensive team can turn it over
        
        # Checking shots 
        test1_df = self.df.loc[self.df["EVENTMSGTYPE"].isin([1,2])][["PLAYER1_TEAM_ID", "POSS"]]
        test1 = compare_series(test1_df["PLAYER1_TEAM_ID"] , test1_df["POSS"])
        if not test1[0]:
            raise Exception(self.game_id, test1[1])
        
        # Checking individual offensive rebounds
        test2_df = self.df.loc[(self.df["EVENTMSGTYPE"]==4) & (self.df["ACTION_DETAILS"]=="OFFENSIVE")][["PLAYER1_TEAM_ID", "POSS"]]
        test2 = compare_series(test2_df["PLAYER1_TEAM_ID"] , test2_df["POSS"])
        if not test2[0]:
            raise Exception(self.game_id, test2[1])
        
        # Checking team offensive rebounds
        test3_df = self.df.loc[(self.df["EVENTMSGTYPE"]==4) & (self.df["ACTION_DETAILS"]=="OFFENSIVE-TEAM")][["PLAYER1_ID", "POSS"]]
        test3 = compare_series(test3_df["PLAYER1_ID"] , test3_df["POSS"])
        if not test3[0]:
            raise Exception(self.game_id, test3[1])
        
        # Only offense can turnover
        test4_df = self.df.loc[self.df["EVENTMSGTYPE"]==5][["PLAYER1_TEAM_ID", "POSS"]]
        test4 = compare_series(test4_df["PLAYER1_TEAM_ID"] , test4_df["POSS"])
        if not test4[0]:
            raise Exception(self.game_id, test4[1])
        
        
        
    
    def preprocess(self, poss_fct_list=[estimate_shotclock, approximate_set_defense], verify=False):
        
        """
        Function that cleans up the PbP dataframe so that we can actually
        extract meaningful information.
        
        The order in which these are called is very important.
        """
        
        self._notify_excess_timeout_technicals()
        
        self._assign_elapsed_time()
        self._assign_remaining_quarter_time()
        self._ft_results()
        self._rebound_type()
        self._shot_type()
        self._handle_simultaneous_rebs_TOs()
        self._add_and1s2()
        self._order_pbp()
        self._adjust_putback_time()
        self._identify_TO_team()
        self._add_inbounds()
        self._propogate_margin()
        self._get_jumpball_winner()
        self._find_flagrant_to()
        self._double_turnovers()
        self._assign_possession()
        self._assign_defense()
        self._assign_clock_on()
        self._assign_chance_number()
        
        self._process_possessions(poss_fct_list)
        
        if verify:
            self._verify_parsing()
        
    
    
    def assign_lineups(self, home_rotation_df, away_rotation_df, fill="PERSON_ID", hash_col=True):
        
        """
        Function that creates 2 new columns, where the content is a list
        of player IDs who were on the court for the given row.
        
        It takes in rotation dataframes as arguments (assumes the format is
        that returned by the nba_api dataframes)
        """
        
        # Set up the empty columns
        
        self.df["HOME_LINEUP"] = [[]] * self.df.shape[0]
        self.df["AWAY_LINEUP"] = [[]] * self.df.shape[0]
    
         
        # Loop though the home team
        for i, row in home_rotation_df.iterrows():
            
            fill_contents = row[fill]
            
            # The rotation dataframe and PbP dataframe dont have the same temporal resolution
            check_in_time_real = row["IN_TIME_REAL"]
            check_out_time_real = row["OUT_TIME_REAL"]
            
            # Very rarely, the API itself will flip the check in time and the 
            # check out time, so if necessary, we flip them here
            if check_out_time_real < check_in_time_real:
                temp = check_in_time_real
                check_in_time_real = check_out_time_real
                check_out_time_real = temp
            
            check_in_time_rounded = math.ceil(check_in_time_real/10)*10
            check_out_time_rounded = math.ceil(check_out_time_real/10)*10
            
            # Find the check in index
            if is_period_marking_timestamp(check_in_time_real):
                
                period = get_period_from_real_check_in_time(check_in_time_real)

                check_in_index = self.df.loc[(self.df["PERIOD"]==period)&(self.df["ELAPSED_TIME"]==check_in_time_rounded)].index[0]
                
            else:
                check_in_index = self.df.loc[(self.df["EVENTMSGTYPE"]==8)&(self.df["ELAPSED_TIME"]==check_in_time_rounded)].index[0] 
                
            # Find the check out index
            if is_period_marking_timestamp(check_out_time_real):
                
                period =  get_period_from_real_check_out_time(check_out_time_real)
                check_out_index = self.df.loc[(self.df["PERIOD"]==period)&(self.df["ELAPSED_TIME"]==check_out_time_rounded)].index[-1]
            
            else:
                
                check_out_index = self.df.loc[(self.df["EVENTMSGTYPE"]==8)&(self.df["ELAPSED_TIME"]==check_out_time_rounded)].index[0] -1
            
            # Add that player to the right cells
            self.df.loc[check_in_index:check_out_index, "HOME_LINEUP"] = \
                self.df.loc[check_in_index:check_out_index, "HOME_LINEUP"].apply(lambda x : x + [fill_contents])
        
        # Loop though the away team
        for i, row in away_rotation_df.iterrows():
            
            fill_contents = row[fill]
            
            # The rotation dataframe and PbP dataframe dont have the same temporal resolution
            check_in_time_real = row["IN_TIME_REAL"]
            check_out_time_real = row["OUT_TIME_REAL"]
            
            # Very rarely, the API itself will flip the check in time and the 
            # check out time, so if necessary, we flip them here
            if check_out_time_real < check_in_time_real:
                temp = check_in_time_real
                check_in_time_real = check_out_time_real
                check_out_time_real = temp
            
            check_in_time_rounded = math.ceil(check_in_time_real/10)*10
            check_out_time_rounded = math.ceil(check_out_time_real/10)*10
            
            # Find the check in index
            if is_period_marking_timestamp(check_in_time_real):
                
                period = get_period_from_real_check_in_time(check_in_time_real)
                check_in_index = self.df.loc[(self.df["PERIOD"]==period)&(self.df["ELAPSED_TIME"]==check_in_time_rounded)].index[0]
            
            else:
                check_in_index = self.df.loc[(self.df["EVENTMSGTYPE"]==8)&(self.df["ELAPSED_TIME"]==check_in_time_rounded)].index[-1] #+ 1
                
            # Find the check out index
            if is_period_marking_timestamp(check_out_time_real):
                
                period = get_period_from_real_check_out_time(check_out_time_real)
                check_out_index = self.df.loc[(self.df["PERIOD"]==period)&(self.df["ELAPSED_TIME"]==check_out_time_rounded)].index[-1]
            
            else:
                
                check_out_index = self.df.loc[(self.df["EVENTMSGTYPE"]==8)&(self.df["ELAPSED_TIME"]==check_out_time_rounded)].index[-1] - 1
            
            
            # Add that player to the right cells
            self.df.loc[check_in_index:check_out_index, "AWAY_LINEUP"] = \
                self.df.loc[check_in_index:check_out_index, "AWAY_LINEUP"].apply(lambda x : x + [fill_contents])


        if hash_col:
            
            def temp(a_list):
                
                output = "-".join(map(str, a_list))
                output = "-" + output + "-"
                return output
            
            self.df["HOME_LINE_HASH"] = self.df["HOME_LINEUP"].apply(temp)
            self.df["AWAY_LINE_HASH"] = self.df["AWAY_LINEUP"].apply(temp)
            
    
    def create_shared_poss_dict(self):
        
        """
        Returns a dictionary of dictionaries of dictonaries:
        - The first level separates offense from defense
        - The second level its to get the player we are interedsted in
        - The third layer is to get the matchup data for the player in question
        
        If a player subs in during a possession, he gets a half possession
        with his teammates and a half possession for himself.
        
        This is not perfect, but makes th code so much easier

        """
        
        home_players = list(set(flatten(self.df["HOME_LINEUP"].tolist())))
        away_players = list(set(flatten(self.df["AWAY_LINEUP"].tolist())))
        all_players = home_players + away_players
        
        # How many times row is on offense with col on floor
        shared_poss_df_att = pd.DataFrame(data=0, index = all_players, columns=all_players)
        # How many times row is on defense with row on floor
        shared_poss_df_def = pd.DataFrame(data=0, index = all_players, columns=all_players)
                  
        home_id, away_id = self._get_teams()
        
        # First worry about possession where the home team is on offense
        # We are storing lists in the dataframe, which are unhashable
        # So we do some janky manual hashing here
        home_attacking = self.df.loc[self.df["POSS"] == home_id][["POSS_ID", "HOME_LINEUP", "AWAY_LINEUP"]].copy()
        home_attacking["HOME_LINE_STR"] = home_attacking["HOME_LINEUP"].apply(lambda x : "_".join(sorted(x)))
        home_attacking["AWAY_LINE_STR"] = home_attacking["AWAY_LINEUP"].apply(lambda x : "_".join(sorted(x)))
        home_attacking.drop(columns=["AWAY_LINEUP", "HOME_LINEUP"], inplace=True)
        home_attacking.drop_duplicates(inplace=True)
        home_attacking_sub_counts = home_attacking["POSS_ID"].value_counts()
        
        home_attacking_lineups = self.df.loc[home_attacking.index, ["POSS_ID","HOME_LINEUP", "AWAY_LINEUP"]]
        
        for i, row in home_attacking_lineups.iterrows():
            
            sub_counts = home_attacking_sub_counts[row["POSS_ID"]]
            home_players = row["HOME_LINEUP"]
            away_players = row["AWAY_LINEUP"]
            all_players = home_players + away_players
            
            for h_player in home_players:
                
                for player in all_players:
                    
                    shared_poss_df_att.loc[h_player, player] += (1/sub_counts)
            
            for a_player in away_players:
                
                for player in all_players:
                    
                    shared_poss_df_def.loc[a_player,player] += (1/sub_counts)
                    
        # Now we do the same for the away team is on offense
        away_attacking = self.df.loc[self.df["POSS"] == away_id][["POSS_ID", "HOME_LINEUP", "AWAY_LINEUP"]].copy()
        away_attacking["HOME_LINE_STR"] = away_attacking["HOME_LINEUP"].apply(lambda x : "_".join(sorted(x)))
        away_attacking["AWAY_LINE_STR"] = away_attacking["AWAY_LINEUP"].apply(lambda x : "_".join(sorted(x)))
        away_attacking.drop(columns=["AWAY_LINEUP", "HOME_LINEUP"], inplace=True)
        away_attacking.drop_duplicates(inplace=True)
        away_attacking_sub_counts = away_attacking["POSS_ID"].value_counts()
        
        away_attacking_lineups = self.df.loc[away_attacking.index, ["POSS_ID","HOME_LINEUP", "AWAY_LINEUP"]]
        
        for i, row in away_attacking_lineups.iterrows():
            
            sub_counts = away_attacking_sub_counts[row["POSS_ID"]]
            home_players = row["HOME_LINEUP"]
            away_players = row["AWAY_LINEUP"]
            all_players = home_players + away_players
            
            for a_player in away_players:
                
                for player in all_players:
                    
                    shared_poss_df_att.loc[a_player, player] += (1/sub_counts)
            
            for h_player in home_players:
                
                for player in all_players:
                    shared_poss_df_def.loc[h_player, player] += (1/sub_counts)
                
        
        shared_off_dic = {}
        for i, row in shared_poss_df_att.iterrows():
            shared_off_dic[i] = row.round(3).to_dict()
        
        shared_def_dic = {}
        for j, row in shared_poss_df_def.iterrows():
            shared_def_dic[j] = row.round(3).to_dict()
        
        output_dic = {"OFF_POSS": shared_off_dic,
                      "DEF_POSS": shared_def_dic}
        
        return output_dic
        
    
    def append_shotchart(self, shotchart_df_list):
        
        """
        Function that appends shot chart data to an existing dataframe
        
        Also works for fouling chart
        """
        
        relevant_shotchart_columns = ["GAME_EVENT_ID","SHOT_ZONE_BASIC", 
                                      "SHOT_ZONE_AREA", "SHOT_ZONE_RANGE", 
                                      "SHOT_DISTANCE", "LOC_X", "LOC_Y"]
        
        shotchart_df = pd.concat(shotchart_df_list)
        
        shotchart_for_merging = shotchart_df[relevant_shotchart_columns]
        
        self.df = self.df.merge(shotchart_for_merging, how="outer", left_on="EVENTNUM", right_on="GAME_EVENT_ID")
    
    




        
        



