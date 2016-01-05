# Introduction
Exercises from the Udacity course on Developing Scalable Apps in Python[1]. The conference app displays a list of conferences and allows users to register for a conference. Users must login with a Google+ account in order to submit new conferences and to register for a conference. 
<br><br>
Conferences include information on the city the conference is located in, the start and end date of the conference, number of seats available, maximum number of attendees, and topics included in the conference.
<br><br>
To run the app on App Engine, a Google Cloud project is needed. Go to: https://console.developers.google.com/project to create a project. Once created, go to APIs & auth->Credentials and then click on OAuth consent screen (top of right panel) and add your email address and a Product name. These are required to run your app on App Engine. 
<br><br> 
To run your own instance of this app, add your Google App Engine Project ID to app.yaml and add your Client ID to the files, static/js/app.js and settings.py.

[1] https://www.udacity.com/course/developing-scalable-apps-in-python--ud858-nd <br>

## Requirements
Python == 2.7

## Usage
See folder ConferenceCentral_FINAL for more details and final running project code.
