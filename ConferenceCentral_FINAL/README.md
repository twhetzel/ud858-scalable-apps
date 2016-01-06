App Engine application for the Udacity training course.

## Products
- [App Engine][1]

## Language
- [Python 2.7][2]

## APIs
- [Google Cloud Endpoints][3]

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

# Application Features
The application uses the Google Datastore and includes and an Entity Kind for 
Conferene, Profile, and Session. <br>
- Conference Entity: represents a Conference (name, description, location, 
date, maximum number of attendees, topics, and organizer). <br>
- Session Entity:  represents a conference session and includes a name, 
date, duration, highlights, speaker, and start time.<br>
- Profile Entity: represents a registered user of the application. Fields 
include display name, T-shirt size, email, and a list of conferences 
registered and sessions in wishlist. <br>
<br>





[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://cloud.google.com/appengine/downloads
[6]: https://localhost:8080/
[7]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
