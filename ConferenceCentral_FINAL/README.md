App Engine application for the Udacity training course.

## Products
- [Google App Engine][1]

## APIs
- [Google Cloud Endpoints][3]

## Language
- [Python 2.7][2]

## Setup Instructions
1. Create a Project on the [Google Developers Console][4]
1. Update the value of `application` in `app.yaml` to the app ID you
   registered in the App Engine Admin Console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Google Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. Run the app with the devserver using `dev_appserver.py DIR` or by using the 
[Google App Engine Launcher application][5]and ensure it's running by visiting
 your local server's address (by default [localhost:8080][6].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][7].
1. Deploy your application.

## Application Features
API Endpoints<br>
- Create, edit, register, and unregister for Conference <br>
- Get conferences user created <br>
- Get details about a Conference <br>
- List all Conferences <br>
- Create Session in a Conference <br>
- List all Sessions in a Conferece <br>
- List Sessions by Type <br>
- List Sessions by Speaker <br>
- Add/delete/get Sessions in Wishlist <br>
- Special Queries for Assignment: Get Sessions that are 30 minutes long and Get sessions that contain the word Android. Also, get Sessions that start bfore 7:00pm and are not workshops.<br>
- Get and save User Profile <br>
- Get conference announcements (Push Task) <br>
- Get Featured Speaker (Push Task) <br>
<br>
All features are enabled at the API level, however only the following functions are implemented in the web front-end: register/unregister user, create conference, register/unregister to conference, filter list of conferences by city, topic, start month, and max attendees, list conferences user created, and list conferences user is registered for.

<br><br>
## Data Model
The application uses the Google Datastore and includes and an Entity Kind for Conferene, Profile, and Session. <br>
- Conference Entity: represents a Conference (name, description, location, 
date, maximum number of attendees, topics, and organizer). <br>
--These properties are modeled as StringProperties: name, description, organizerId, topics (enumeration), and city. Topics and name are required since these represent the minimal information to describe a conference. <br>
-- These properties are modeled as a DateProperty: startDate and endDate.<br>
-- These properties are modeled as an IntegerProperty: month, maxAttendees, and seatsAvailable<br>
- Session Entity:  represents a conference session and includes a name, 
date, duration, highlights, speaker, and start time.<br>
-- These properties are modeled as a StringProperty: websafeConferenceKey, name, speaker, and typeOfSession (enumeration). Name is required.<br>
-- These properties are modeled as an IntegerProperty: duration<br>
-- These properties are modeled as a DateTimeProperty: date<br>
-- These properties are modeled as a TimeProperty: startTime<br>
- Profile Entity: represents a registered user of the application. Fields 
include display name, T-shirt size, email, and a list of conferences 
registered and sessions in wishlist. 
<br><br>
The Profile Entity is the Ancestor to a Conference Entity and the Conference Entity is an anccestor to the Session Entity.
<br>

<br><br>
## Problematic Query
Implement a query for conference sessions that are not workshops and are not after 7pm.
<br>
The problem is that an inequality filter in Datastore can be applied to at most one property. Filtering 
for sessions that are not workshops involves the typeOfSession property and the restriction for sessions
not after 7pm involves the startTime property, therefore two properties are involved which need an 
inequality filter.

The solution implemented to solve this is to first get all sessions for a given conference that are 
not of the type workshops. The resulting sessions are then examined for sessions that are before 7pm. This order was selected because there are multiple types of sessions and querying for session not equal to workshops is more straighforward/efficient than the alternative of querying for all sessions before 7pm and then having to iterate through these sessions to check if they are of the type workshops. Using the method implemented has Datastore the majority of the filtering work.

<br><br>

[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://cloud.google.com/appengine/downloads
[6]: https://localhost:8080/
[7]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
