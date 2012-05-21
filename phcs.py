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


import threading
import time,datetime
import Queue

try:
    import json
except ImportError:
    print "json not found\ninstall with pip json"
    exit(1)
try:
    import gflags
    import httplib2

    from apiclient.discovery import build
    from oauth2client.file import Storage
    from oauth2client.client import OAuth2WebServerFlow
    from oauth2client.tools import run

except ImportError:
    print "gdata services not found\nhg clone https://google-api-python-client.googlecode.com/hg/ google-api-python-client"
    exit(1)
try:
    import pyttsx
except ImportError:
    print "pyttsx not found\ninstall with pip pyttsx"
try:
    import requests
except ImportError:
    print "requests not foudd\n, install with pip requests"

class phi():
    def say(self,string):
        self.say_queue.put(string)

    def __init__(self):
        self.__VERSION__ = "0.0.1"
        #Locks, Queues and Semaphore
        self.say_queue = Queue.Queue() 
        self.lock = threading.Lock()
        #speak thread
        self.speak = voice_thread(self)
        self.speak.start()
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
                self.voice_engine.say(string)
                print "Saying: %s" %string
                self.phi.lock.release()
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
        wunderground_API_KEY = "187769790cf46747"
        self.base_url = "http://api.wunderground.com/api/%s/" % (wunderground_API_KEY)

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
        url = self.base_url+"/conditions/forecast/astronomy/tide/q/08820.json"
        weather = json.loads(requests.get(url).content)
        current_temp = weather['current_observation']['temp_f']
        current_condition = weather['current_observation']['weather']
        current_humidity = weather['current_observation']['relative_humidity']
        current_string = "It is currently %d degrees and %s with a humidity of %s." %(current_temp,current_condition,current_humidity)
        forcast_high = weather['forecast']['simpleforecast']['forecastday'][0]['high']['fahrenheit']
        forcast_low = weather['forecast']['simpleforecast']['forecastday'][0]['low']['fahrenheit']
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
            client_id='793289940997.apps.googleusercontent.com',
            client_secret='icJtNzYqfjUlzkFWlguwbQBE',
            scope='https://www.googleapis.com/auth/calendar',
            user_agent='phi.'+self.phi.__VERSION__)
        storage = Storage('calendar.dat')
        credentials = storage.get()
        if credentials is None or credentials.invalid == True:
          credentials = run(FLOW, storage)
        http = httplib2.Http()
        http = credentials.authorize(http)
        self.service = build(serviceName='calendar', version='v3', http=http,
               developerKey='AIzaSyAUgnBETcO9ISvhfKuJMjBvbHYxak7DNcU')



    def get_today_events(self):
        #sorting doesn't work correctly
        full_events=[]
        hour_events=[]
        returnString = ""
        now = datetime.datetime.now()
        start_date = "%d-%02d-%02dT00:00:00.000-04:00" % (now.year,now.month,now.day)
        end_date = "%d-%02d-%02dT00:00:00.000-04:00" % (now.year,now.month,now.day+2)
        calendars =self.service.calendarList().list().execute()
        for calendar in calendars['items']:
            id = calendar['id']
            events = self.service.events().list(calendarId=id,timeMin=start_date,timeMax=end_date).execute()
            if 'items' in events:
                for event in events['items']:
                    event_name = event['summary']
                    event_start = event['start']
                    if 'date' in event_start:
                        full_events.append(event_name)
                    else:
                        hour = int(event_start['dateTime'][11:13])
                        minu = int(event_start['dateTime'][14:16])
                        ampm = "A.M."
                        if hour >= 12:
                            ampm = "P.M."
                            if hour >= 13:
                                hour -= 12
                        elif hour == 0:
                            hour = 12
                        if minu == 0:
                            time = "%d o'clock %s" % (hour,ampm)
                        else:
                            time = "%d %d %s" % (hour,minu,ampm)
                        event = {'name':event_name,'time_str':time,'time':event_start['dateTime']}
                        index = 0
                        for oldEvent in hour_events:
                            if oldEvent['time'] < event['time']:
                                index = hour_events.index(oldEvent)+1
                                break
                        hour_events.insert(index,event)
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

