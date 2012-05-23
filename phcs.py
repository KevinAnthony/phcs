#!/usr/bin/env python

#
#    PHCS  Personal Home Computerized Secretary
#    Copyright (C) 2012 <kevin.s.anthony@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys,os
import threading
import time,datetime
import argparse
import Queue
import ConfigParser

exitError=False
try:
    import json
except ImportError:
    print "json not found\nsudo pip install json"
    exitError=True
try:
    import gflags
    import httplib2

    from apiclient.discovery import build
    from oauth2client.file import Storage
    from oauth2client.client import OAuth2WebServerFlow
    from oauth2client.tools import run
except ImportError:
    print "Google API Client not found\nsudo pip install google-api-python-client"
    exitError=True
try:
    import pyttsx
except ImportError:
    print "pyttsx not found\nsudo pip install pyttsx"
    exitError=True
try:
    import requests
except ImportError:
    print "requests not found\nsudo pip install requests"
    exitError=True
try:
    import dateutil.parser
except ImportError:
    print "date utilitis not found\nsudo pip install dateutils"
if exitError:
    exit(1)

class phi():
    def say(self,string):
        self.say_queue.put(string)
    
    def __read_config(self):
        config = ConfigParser.ConfigParser()
        config.readfp(open(os.path.abspath(os.path.join(sys.path[0],'settings.py'))))
        return config

    def __process_command_line_arguments(self,config):
        parser = argparse.ArgumentParser(description='Persional Home Computrized Secritary')
        parser.add_argument("-d","--debug",action="store_true",dest="debug",default=config.get("MAIN","DEBUG"),help="Enable Debugging")
        parser.add_argument("-s","--no-speak",action="store_false",dest="nospeak",default=config.get("MAIN","SPEAK"),help="Disable TTS")
        parser.add_argument("-z""--zipcode",action="store",dest="zipcode",default=config.get("MAIN","ZIPCODE"),help="Change Zipcode")
        parser.add_argument("-u","--units",action="store",dest="units",default=config.get("MAIN","UNITS"),help="Change Units Imperial/Metric")
        
        parser.add_argument("--wunderground",action="store",dest="wunderground",default=config.get("API","WUNDERGROUND_KEY"),help="Weather Underground API Key")
        parser.add_argument("--googleid",action="store",dest="googid",default=config.get("API","GOOGLE_ID"),help="Google ID Key")
        parser.add_argument("--googlesecret",action="store",dest="googsecret",default=config.get("API","GOOGLE_SECRET"),help="Google Secret Key")
        parser.add_argument("--googledevkey",action="store",dest="googdevkey",default=config.get("API","GOOGLE_DEVEL_KEY"),help="Google Developer Key")
        
        parser.parse_args(namespace=self)
        unit = self.units.lower()

        if unit in ('i','imperial'):
            self.units='i'
        elif unit in ('m','metric'):
            self.units="m"
        else:
            print "%s not a recognized value for units\nexiting" % unit
            exit(1)
        

    def __init__(self):
        self.__VERSION__ = "0.0.2"
        config = self.__read_config()
        self.__process_command_line_arguments(config)
        #Locks, Queues and Semaphore
        self.say_queue = Queue.Queue() 
        self.lock = threading.Lock()
        #speak thread
        self.speak_thread = voice_thread(self)
        self.speak_thread.start()
        #all other threads
        self.taw_thread = time_and_weather_thread(self)
        self.taw_thread.start()
        self.cal_thread = calendar_thread(self)
        self.cal_thread.start()

class voice_thread(threading.Thread):
    
    def __init__(self,phi):
        threading.Thread.__init__(self)
        self.voice_engine = pyttsx.init()
        self.voice_engine.setProperty('rate', self.voice_engine.getProperty('rate')-50)
        self._stopevent = threading.Event()
        self.phi = phi

    def run(self):
        while not self._stopevent.isSet():
            while not self.phi.say_queue.empty():
                self.phi.lock.acquire()
                string = self.phi.say_queue.get()
                if self.phi.debug:
                    print "Saying: %s" % string
                if self.phi.nospeak:
                    self.voice_engine.say(string)
                self.phi.say_queue.task_done()
                self.phi.lock.release()
            if self.phi.nospeak:
                self.voice_engine.runAndWait()
           
    def join(self,timeout=None):
        self._stopevent.set()
        self.voice_engine.stop()
        threading.Thread.join(self,timeout)

class time_and_weather_thread(threading.Thread):
    def __init__(self,phi):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        self.phi = phi
        self.base_url = "http://api.wunderground.com/api/%s/" % (self.phi.wunderground)

    def run(self):
        if not self._stopevent.isSet():
            #Time and Weather have to come first, everything else second
            self.phi.lock.acquire()
            time = self.get_time()
            weather = self.get_weather()
            self.phi.say(time)
            self.phi.say(weather)
            self.phi.lock.release()

    def get_time(self):
        now = datetime.datetime.now()
        greeting = "Morning"
        if now.hour >= 12 and now.hour < 17:
            greeting = "Afternoon"
        if now.hour >= 17:
            greeting = "Evening"
        return "Good %s" %(greeting) + now.strftime(" it is %A %B %dth.  The Time is now %I %M %p")

    def get_weather(self):
        url = self.base_url+"/conditions/forecast/astronomy/tide/q/"+self.phi.zipcode+".json"
        weather = json.loads(requests.get(url).content)
        if self.phi.units == "i":
            current_temp = weather['current_observation']['temp_f']
            forcast_high = weather['forecast']['simpleforecast']['forecastday'][0]['high']['fahrenheit']
            forcast_low = weather['forecast']['simpleforecast']['forecastday'][0]['low']['fahrenheit']
        if self.phi.units == "m":
            current_temp = weather['current_observation']['temp_c']
            forcast_high = weather['forecast']['simpleforecast']['forecastday'][0]['high']['celsius']
            forcast_low = weather['forecast']['simpleforecast']['forecastday'][0]['low']['celsius']
        current_condition = weather['current_observation']['weather']
        current_humidity = weather['current_observation']['relative_humidity']
        current_string = "It is currently %d degrees and %s with a humidity of %s." %(current_temp,current_condition,current_humidity)
        forcast_condition = weather['forecast']['simpleforecast']['forecastday'][0]['conditions']
        forcast_string = "Today will have a high of %s degrees low of %s degrees, condistions are: %s." % (forcast_high,forcast_low,forcast_condition)
        return (current_string+" "+forcast_string)

    def join(self,timeout=None):
        self._stopevent.set()
        threading.Thread.join(self,timeout)

class calendar_thread(threading.Thread):

    def __init__(self,phi):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        self.phi = phi
        self.__FLAGS = gflags.FLAGS

    def run(self):
        if not self._stopevent.isSet():
            self.login()
            events = self.get_today_events()
            self.phi.lock.acquire()
            self.phi.say(events)
            self.phi.lock.release()
    
    def login(self):
        FLOW = OAuth2WebServerFlow(
            client_id=self.phi.googid,
            client_secret=self.phi.googsecret,
            scope='https://www.googleapis.com/auth/calendar',
            user_agent='phi.'+self.phi.__VERSION__)
        storage = Storage('calendar.dat')
        credentials = storage.get()
        if credentials is None or credentials.invalid == True:
          credentials = run(FLOW, storage)
        http = httplib2.Http()
        http = credentials.authorize(http)
        self.service = build(serviceName='calendar', version='v3', http=http,
               developerKey=self.phi.googdevkey)



    def get_today_events(self):
        #sorting doesn't work correctly
        full_events=[]
        hour_events=[]
        returnString = ""
        now = datetime.datetime.now()
        start_date = "%d-%02d-%02dT00:00:00.000-04:00" % (now.year,now.month,now.day)
        end_date = "%d-%02d-%02dT23:59:59.000-04:00" % (now.year,now.month,now.day)
        calendars =self.service.calendarList().list().execute()
        for calendar in calendars['items']:
            id = calendar['id']
            events = self.service.events().list(calendarId=id,timeMin=start_date,timeMax=end_date).execute()
            if 'items' in events:
                for event in events['items']:
                    event_name = event['summary'].lstrip()
                    event_start = event['start']
                    if 'date' in event_start:
                        full_events.append(event_name)
                    else:
                        time = dateutil.parser.parse(event_start['dateTime']).astimezone(dateutil.tz.tzlocal())
                        if time.strftime("%p") == "AM":
                            ampm = "A.M."
                        else:
                            ampm = "P.M."
                        if time.minute == 0:
                            timestr = "%d o'clock %s"%(int(time.strftime("%I")),ampm)
                        else:
                            timestr = "%d %d %s"%(int(time.strftime("%I")),time.minute,ampm)
                        event = {'name':event_name,'time_str':timestr,'time':time}
                        hour_events.append(event)
       
        hour_events = sorted(hour_events,key=lambda event: event['time'])

        numberEvents = len(full_events)+len(hour_events)
        if numberEvents == 0:
            return "You have nothing planned for today"
        else:
            if len(hour_events) > 0:
                if len(hour_events) == 1:
                    returnString = "You have %d appointment today.\n" % len(hour_events)
                else:
                    returnString = "You have %d appointments today.\n" % len(hour_events)
                for event in hour_events:
                    returnString+="%s at %s.\n" % (event['name'],event['time_str'])
            if len(full_events) > 0:
                if len(full_events)==1:
                    returnString += "You have %d note.\n" %len(full_events)
                else:
                    returnString += "You have %d notes.\n" %len(full_events)
                for event in full_events:
                    returnString+="%s\n"%event
            return returnString
        return "You have nothing planned for today"
                    
    def join(self,timeout=None):
        self._stopevent.set()
        threading.Thread.join(self,timeout)

class skeloton_thread(threading.Thread):

    def __init__(self,phi):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        self.phi = phi

    def run(self):
        while not self._stopevent.isSet():
            None    
    
    def join(self,timeout=None):
        self._stopevent.set()
        threading.Thread.join(self,timeout)
     
if __name__ == "__main__":
    p=phi()
    stopEvent = threading.Event()
    while not stopEvent.isSet():
        try:
            time.sleep(1)
        except(KeyboardInterrupt):
            stopEvent.set()
            print "Exiting"

