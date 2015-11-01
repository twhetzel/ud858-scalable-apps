# Introduction
Exercises from the Udacity course on Scalable apps (ud858). The conference app displays a list of conferences and allows users to register for a conference. Users must login with a Google+ account in order to submit new conferences and to register for a conference. 
<br>
Conferences include information on the city the conference is located in, the start and end date of the conference, number of seats available, maximum number of attendees, and topics included in the conference.
<br>
To run the app on App Engine, a Google Cloud project is needed. Go to: https://console.developers.google.com/project to create a project. Once created, go to APIs & auth->Credentials and then click on OAuth consent screen (top of right panel) and add your email address and a Product name. These are required to run your app on App Engine. 
<br> 
To run your own instance of this app, add your Google App Engine Project ID to app.yaml and add your Client ID to the files, static/js/app.js and settings.py.


## Requirements
Python == 2.7

## Usage
TODO: Add documentation on how to run on local host and deploy to App Engine 