# -*- coding: utf-8 -*-
"""Python code for analysis"""

#import packages needed for this code
import pandas as pd
import datetime as dt
import astral
import astral.sun
from astral.geocoder import database, lookup
from statistics import mean
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

#input file is Jason's output. read with pandas
df = pd.read_parquet("SeaUgradTimingAnalysis.parquet",engine="auto")
#set the date column to be in a datetime type instead of string/obj
df["Date"] = pd.to_datetime(df["Date"])
#index needs to be reset because there were multiple rows with the same index which messed with my later functions
df = df.reset_index()

"""Adding solar noon and midnight"""

#set the city to Seattle for astral
city = lookup("Seattle",database())

#define a function to calculate midnight and noon for the city
def midnoon(df,row):
  """
  Parameters
  ----------
  df : dataframe
    The dataframe that has the date column that you want to calculate midnight and noon for
  row: int
    Row of cell that sould be converted

  Returns
  -------
  list?
    2 datetime values. First is midnight, second is noon
  """
  date1 = df["Date"][row].to_pydatetime().date() + dt.timedelta(days=1)
  mid = astral.sun.midnight(city.observer, date=date1,tzinfo="America/Los_Angeles")
  noon = astral.sun.noon(city.observer, date=date1,tzinfo="America/Los_Angeles")
  return dt.datetime.combine(mid.date(),mid.time()),dt.datetime.combine(noon.date(),noon.time())

#create a new column in the dataframe with the midnight times
mids = []
for a in range(len(df)):
    mids.append(midnoon(df,a)[0])
df["midnight"] = mids

#create a new column in the dataframe with the noon times
noons = []
for a in range(len(df)):
    noons.append(midnoon(df,a)[1])
df["noon"] = noons

#function that functions like Jason's MSLM. It converts a datetime into minutes since last midnight?
#https://github.com/jasongfleischer/SALA/blob/01994be853a20449dea0eed9ae0e69099d554695/Analyze%20by%20person.ipynb
def conv(df,col,row):
  """
  Parameters
  ----------
  df: dataframe
  col: str
    Name of the column that should be converted
  row: int
    Row of cell that should be converted

  Returns
  -------
  int
    Integer that equals number of minutes since midnight
  """
def conv(df,col,row):
  date1 = dt.datetime.combine(df["Date"][row].to_pydatetime().date(), dt.time(0, 0, 0))
  converted =(df[col][row].to_pydatetime()-date1).total_seconds()/60
  return converted

#convert midnight column into minutes since midnight
mid_mslm = []
for a in range(len(df)):
    mid_mslm.append(conv(df,"midnight",a))
df["Midnight"] = mid_mslm

#convert noon column into minutes since midnight
noon_mslm = []
for a in range(len(df)):
    noon_mslm.append(conv(df,"noon",a))
df["Noon"] = noon_mslm

"""Add the sleep data (instead of actiwatch data)"""

#get the cleaned onset and offset data and merge with the subjects that are included
ref = pd.read_csv("subjects_included.csv",usecols=['Quarter', 'Year', 'Class', 'Subject ID'])
sleepdata = pd.read_csv("Sleep_Onset_Offset_All_Years.csv")
sleepdata = sleepdata.rename(columns={"subject":"Subject ID"})
sleepdata["onset"] = pd.to_datetime(sleepdata["onset"])
sleepdata["offset"] = pd.to_datetime(sleepdata["offset"])
df2 = ref.merge(sleepdata,how="left")
df2 = df2.reset_index(drop=True)

#Jason has a column called "Date" which seems to be the "onset" date. But, if the onset is after midnight, it's the day before. 
#This function returns a date that follows that definition
def onset_date(df,row):
  """
  Parameters
  ----------
  df: dataframe object
  row: int

  Returns
  -------
  datetime obj
  """
  if pd.isna(df["onset"][row]):
      date1 = df["offset"][row].to_pydatetime().date() - dt.timedelta(days=1)
  else:
      time1 = df["onset"][row].time()
      if time1 < dt.time(12):
          date1 = df["onset"][row].to_pydatetime().date() - dt.timedelta(days=1)
      else:
          date1 = df["onset"][row].date()
  return date1

#create a date column in the second dataframe and set the dtype to datetime
dates = []
for a in range(len(df2)):
    dates.append(onset_date(df2,a))
df2["Date"] = dates
df2["Date"] = df2["Date"].astype('datetime64')

#change object to specified dtype to make merging possible
df['Year']=df['Year'].astype(int)
df['Class']=df['Class'].astype(int)
df['Subject ID']=df['Subject ID'].astype(int)
df['Date']=df['Date'].astype('datetime64')

#just checking how the dataframe looks
#df2.to_csv("subjects_sleep.csv")

#new merged dataframe
df3 = df.merge(df2,how="right",on=["Date","Quarter","Year","Class","Subject ID"])

#convert the onset and offset times to minutes since midnight
on_mslm = []
for a in range(len(df3)):
    on_mslm.append(conv(df3,"onset",a))
df3["Onset_MSLM"] = on_mslm
off_mslm = []
for a in range(len(df3)):
    off_mslm.append(conv(df3,"offset",a))
df3["Offset_MSLM"] = off_mslm

#drop rows where the values in the "Out of School" column are empty. This is because there were some dates in the second dataframe that were not in Jason's dataset. Including these dates without a defined in/out of school messes with the make clock plots function
df3 = df3.dropna(axis=0,subset=["OutofSchool"])

#save the dataframe as a CSV to check if the dataframe is ok
#df3.to_csv("merge check.csv")

"""Clock plots"""

#Jason wrote this function
def map_mins_to_rads(dseries):
  med = dseries.median()
  p25 = dseries.quantile(0.25)
  p75 = dseries.quantile(0.75)    
  return ([x/1440.0*2*np.pi for x in np.arange(p25,p75)], med/1440.0*2*np.pi)

#Jason also wrote this
def tprint(mins):
  h = int(mins/60.)
  m = int( ( mins - h*60) )
  if h>=24.0:
      h = h-24
  return '{:02d}:{:02d}'.format(h,m)

#I wrote this before Jason updated his code, but when I removed it, something broke. It's not used so removing it should be fine
def convert_mins(num):
  duration = dt.timedelta(minutes=num)
  days, seconds = duration.days, duration.seconds
  hours = days * 24 + seconds // 3600
  minutes = (seconds % 3600) // 60
  if hours >24:
      hours -=24
  return str(hours).zfill(2)+":"+str(minutes).zfill(2)

#Jason wrote this function, but I updated it to include the solar noon and midnight on the clock plots
def make_clock_plots( timingData, Groupby, Thresholds=False, figsize=(5,10) ):
  sns.set_style("white")
  
  if not Thresholds:
      Thresholds = timingData.Threshold.unique()
      
  gcols=sns.color_palette('Set2',7)

  boxrad=0.3/len(Thresholds) 
  mw = 2*np.pi/1440
  boxsep = 1.1

  Ng = len(timingData[Groupby].unique())
  f = plt.figure(figsize=figsize)
  
  for gn, grp in enumerate(timingData[Groupby].unique()):
    ax = f.add_subplot(Ng,1,gn+1, projection='polar')
    tbg = timingData[timingData[Groupby]==grp]
    sunrise=(tbg['Sunrise']*60).median() #now its in hours, used to be timestamp #.apply(timestamp_to_minutes).median()
    sunset=(tbg['Sunset']*60).median() #now its in hours, used to be timestamp #.apply(timestamp_to_minutes).median()
    
    dark=[x/1440.0*2*np.pi for x in np.arange(0,sunrise)]
    ax.bar(dark, np.ones_like(dark), width=0.02, color=[0.42,0.42,0.42], linewidth=0)
    dark=[x/1440.0*2*np.pi for x in np.arange(sunset,1440)]
    ax.bar(dark, np.ones_like(dark), width=0.02, color=[0.42,0.42,0.42], linewidth=0)
    
    midnight = (tbg["Midnight"]).median()
    noon = (tbg["Noon"]).median()
    noon_dark = [noon/1440.0*2*np.pi]
    ax.bar(noon_dark,np.ones_like(noon_dark), width=0.05, color='#ffeebf', linewidth=0)
    mid_dark = [midnight/1440.0*2*np.pi]
    ax.bar(mid_dark,np.ones_like(mid_dark), width=0.05, color='#ffeebf', linewidth=0)
    
    lli=[]
    lll=[]
    for i,thr in enumerate(Thresholds):
      added = False
      tbgt = timingData[(timingData[Groupby]==grp)&(timingData['Threshold']==thr)]
      onset = 4*60+tbgt['Mins to FL from 4AM']
      offset = 4*60+tbgt['Mins to LL from 4AM']
      onbox, onmed = map_mins_to_rads(onset)
      offbox, offmed = map_mins_to_rads(offset)        
      ll=ax.bar(onbox, np.full(len(onbox), boxrad), 
                width=mw, bottom=1.0-(i+1)*boxrad*boxsep, 
                color=gcols[i], linewidth=0, alpha=1.)
      _ =ax.bar(onmed, boxrad, 
                width=0.02, bottom=1.0-(i+1)*boxrad*boxsep, 
                color=[0.2,0.2,0.2], linewidth=0)
      # for weird small datasets there can be low threshold light onset without offset; 
      # this craziness is to take care of that odd case!
      if (len(ll)>0): 
        lli.append(ll)
        lll.append('{:3d}lx {}-{}'.format(thr, tprint(onset.median()), tprint(offset.median())) )
        added = True
      
      ll=ax.bar(offbox, np.full(len(offbox), boxrad), 
                width=mw, bottom=1.0-(i+1)*boxrad*boxsep, 
                color=gcols[i], linewidth=0, alpha=1.)
      _ =ax.bar(offmed, boxrad, 
                width=0.02, bottom=1.0-(i+1)*boxrad*boxsep, 
                color=[0.2,0.2,0.2], linewidth=0) 
      if (len(ll)>0) and (not added):
        lli.append(ll)
        lll.append('{}lx'.format(thr))
    offset = tbgt['Offset_MSLM']-1440
    onset = tbgt['Onset_MSLM']
    offbox, offmed = map_mins_to_rads(offset)
    onbox, onmed = map_mins_to_rads(onset)
    p=ax.bar(offbox, np.full(len(offbox), 2*boxrad), 
              width=mw, bottom=1.0-(i+4)*boxrad*boxsep, 
              color=gcols[-2], linewidth=0, alpha=1.)
    _ =ax.bar(offmed, 2*boxrad, width=0.02, 
              bottom=1.0-(i+4)*boxrad*boxsep, 
              color=[0.2,0.2,0.2], linewidth=0)
    ll=ax.bar(onbox, np.full(len(onbox), 2*boxrad), 
              width=mw, bottom=1.0-(i+4)*boxrad*boxsep, 
              color=gcols[-2], linewidth=0, alpha=1.)
    _ =ax.bar(onmed, 2*boxrad, 
              width=0.02, bottom=1.0-(i+4)*boxrad*boxsep, 
              color=[0.2,0.2,0.2], linewidth=0)
    lli.append(ll)
    lll.append('Sleep {}-{}'.format(tprint(onset.median()), tprint(offset.median())) )

    thetat = np.arange(0,6)*60
    thetalbl = ['00:00','04:00','08:00','12:00','16:00','20:00']
    ax.set_thetagrids(thetat, labels=thetalbl) #with new matplotlib this parameter is gone frac=1.27)
    ax.set_theta_direction(-1)
    ax.set_theta_offset(np.pi)
    ax.set_rticks([])  # less radial ticks
    ax.set_rmax(1.0)
    ax.grid(False)
    
    #if gn+1==Ng:
    ax.legend(lli,lll,loc=[1.01,0.01],prop={'family': 'monospace'})
    
    nuids = len(tbg.UID.unique())
    ndays = len(tbg.Date.unique())
    pdays = len(tbgt[['UID','Date']].drop_duplicates())
    title = "{}={}: {} subjects, {} dates, {} person-days".format(Groupby,grp,nuids,ndays,pdays)
    ax.set_title(title, y = 1.02) #loc='center', ha='center', va='bottom')
    
      
  plt.subplots_adjust(wspace = 1.2)
  #plt.figtext(0.25,0.5,"Sunrise: {:.2f}, Sunset: {:.2f}, Midnight: {:.2f}, Noon: {:.2f}".format(sunrise, sunset, midnight, noon))

#create the clock plots in png and eps formats
quarters = ["Winter","Spring","Summer","Fall"]
for Q in quarters:
  print(Q)
  make_clock_plots( df3.query('Quarter == @Q'), 'OutofSchool', Thresholds=[500,50,5], figsize=(10,10))
  plt.suptitle(Q+' quarter')
  #plt.tight_layout()
  plt.savefig('light figures 2 test/clockplot-'+Q+'-quarter.png',dpi=300)
  plt.savefig('light figures 2 test/clockplot-'+Q+'-quarter.eps',dpi=300,metadata='eps')
  plt.close()
  print("done with "+Q)
print("done")



