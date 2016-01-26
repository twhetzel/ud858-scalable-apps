#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'plwhetzel@gmail.com (Trish Whetzel)'

import time

from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize

from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForm
from models import SessionQueryForms
from models import SESSION_CONTAINER
from models import SPEAKER_CONTAINER

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKERS_KEY = "FEATURED_SPEAKERS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

WISHLIST_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    sessionKey=messages.StringField(1),
)


# - - - Define subclass of remote.Service  - - - - - - - - -

@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException('Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    # Create a Conference 
    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    # Update Conference details
    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    # Get details about a Conference 
    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException('No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    # Get Conferences you have created 
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], 
                filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field 
            in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    # Get list of all Conferences    
    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) 
                for conf in conferences]
        )


# - - - Session objects - - - - - - - - - - - - - - - - - - -

    def _createSessionObject(self, request):
        """Create a Session object."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # Make sure a websafeConferenceKey is provided (for testing)
        if not request.websafeConferenceKey:
            raise endpoints.BadRequestException("Session 'websafeConferenceKey' \
                field required. Use form filters to add websafeConferenceKey")

        # get key of conference to create sessions for
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        # check that startTime is provided
        if not data['startTime']:
            raise endpoints.BadRequestException("Start time is required")
        else:
            data['startTime'] = datetime.strptime(data['startTime'], '%H:%M').time()
            
        # check that date is provided     
        if not data['date']:
            raise endpoints.BadRequestException("Date is required.")
        else:
            data['date']= datetime.strptime(data['date'], '%Y-%m-%d').date()

        wsck = data['websafeConferenceKey']
        p_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        
        c_id = Session.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Session, c_id, parent=p_key)
      
        data['key'] = c_key

        Session(**data).put()
        
        # get speaker name
        newSessionSpeaker = data['speaker']
        print "** newSessionSpeaker: ", newSessionSpeaker

        # Push task to determine if speaker of this new 
        # session should be set as the featured speaker
        taskqueue.add(params={'newSessionSpeaker': newSessionSpeaker,
            'websafeConferenceKey': wsck},
            url='/tasks/set_featured_speaker'
        )
        return request


    # Use Push Task to determine featured speaker, a speaker that has 
    # more than 1 session in a conference 
    @staticmethod
    def _cacheFeaturedSpeaker(newSessionSpeaker, websafeConferenceKey):
        """Called when a new session is created and evaluates whether the 
        speaker of the new session should be set as the featured speaker 
        for the conference.
        """     
        
        # get all sessions in this conference by this speaker 
        sessions = Session.query(Session.websafeConferenceKey == websafeConferenceKey)\
        .filter(Session.speaker == newSessionSpeaker)
        
        count = sessions.count()
        
        if count >= 1:
            for session in sessions:
                separator = ", "
                thisSpeakersSessions = separator.join([session.name for session in sessions])
                
            speakerNameAndSessions = "Featured Speaker is "+newSessionSpeaker+\
            " presenting sessions "+thisSpeakersSessions

            memcache.set(MEMCACHE_FEATURED_SPEAKERS_KEY, speakerNameAndSessions)


    # Get Featured Speaker from Memcache
    @endpoints.method(message_types.VoidMessage, StringMessage, 
        path="featuredSpeaker", 
       http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Get Featured Speaker from Memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_SPEAKERS_KEY) or "")

    
    # Create a new Session
    @endpoints.method(SessionForm, SessionForm, path='session', 
        http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session for a conference."""
        return self._createSessionObject(request)

    
    # Get Sessions for a Conference
    @endpoints.method(SESSION_CONTAINER, SessionForms, 
        path='getConferenceSessions/{websafeConferenceKey}',
        http_method='GET',
        name='getConferenceSessions')
    def getConferenceSessions(self, request):
        '''Given a conference, return all sessions'''
        # make sure user is logged in
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        
        # get conference key to use to find all sessions in this conference
        conferenceKey = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        ck = getattr(conferenceKey, "key")
        
        # get all sessions in this conference
        sessions = Session.query(Session.websafeConferenceKey == request.websafeConferenceKey)
        
        # return sessions in this conference
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    
    def _copySessionToForm(self, sess):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(sess, field.name):
                # convert Date to date string; just copy others
                # For converted fields, only do operation if not null # TODO
                if field.name == 'date':
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                elif field.name == 'startTime':
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                else:
                    setattr(sf, field.name, getattr(sess, field.name))        
            elif field.name == "websafeConferenceKey":
                setattr(sf, field.name, sess.key.urlsafe())
        sf.check_initialized()
        return sf

 
    def _getQuerySession(self, request):
        """Return formatted query from the submitted filters."""
        q = Session.query() 
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Session.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Session.name)

        for filtr in filters:
            if filtr["field"] in ["duration"]:
                filtr["value"] = int(filtr["value"])
            elif filtr["field"] in ["date", "startTime"]:
                filtr["value"] = str(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], 
                filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q
    

    # Get Sessions by Type 
    @endpoints.method(SESSION_CONTAINER, SessionForms,
        path='getConferenceSessionsByType/{websafeConferenceKey}/{typeOfSession}',
        http_method='POST',
        name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        '''Given a conference, return all sessions of a specified type'''
        
        # make sure user is logged in
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # get conference key to use to find all sessions in this conference
        conferenceKey = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        ck = getattr(conferenceKey, "key")
        
        # create ancestor query to get all sessions in this conference
        sessions = Session.query(Session.websafeConferenceKey == request.websafeConferenceKey)
        sessions = sessions.filter(Session.typeOfSession == sessionType) 
        
        # return sessions in this conference
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )


    # Get Sessions by Speaker
    @endpoints.method(SPEAKER_CONTAINER, SessionForms,
        path='getSessionsBySpeaker/{speaker}',
        http_method='POST',
        name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        '''Given a speaker, return all sessions given by this particular speaker, across all conferences'''
        
        # make sure user is logged in
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # get speaker value from form request
        sessionSpeakerOfInterest = request.speaker
        print "** Speaker: ", sessionSpeakerOfInterest
        
        # store all session objects across all conferences where this speaker is presenting
        all_sessions = []
        # query for conferences
        conferences = Conference.query()
        for conf in conferences:
            ck = getattr(conf, 'key')
            wsck = ck.urlsafe()
            
            # For each conference, get Sessions for the Conference filtered by Speaker
            sessions = Session.query(Session.websafeConferenceKey == wsck)
            sessions = sessions.filter(Session.speaker == sessionSpeakerOfInterest)
            
            for session in sessions:
                all_sessions.append(session)

        # return sessions in all conferences
        return SessionForms(
            items=[self._copySessionToForm(session) for session in all_sessions]
        )


# - - - Sessions in User Wishlist - - - - - - - - - - - - - - 
    # Add sessions to wishlist 
    @ndb.transactional(xg=True)
    def _sessionWishlistRegistration(self, request, reg=True):
        """Add or remove Session from Wishlist."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile
        
        # check if session exists given sessionKey
        # get session; check that it exists
        session_key = request.sessionKey
        
        session = ndb.Key(urlsafe=session_key).get()
        
        if not session:
            raise endpoints.NotFoundException('No session found with key: %s' % session_key)
   
        # add session to wishlist
        if reg:
            # check if user already registered otherwise add
            if session_key in prof.sessionKeysForWishlist:
                raise ConflictException("You have already added this session to your wishlist")
            # add session to wishlist
            prof.sessionKeysForWishlist.append(session_key)
            retval = True

        # remove session from wishlist
        else:
            # check if session already in wishlist
            if session_key in prof.sessionKeysForWishlist:
        
                # remove session from wishlist
                prof.sessionKeysForWishlist.remove(session_key)
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        return BooleanMessage(data=retval)


    # Add Session to Wishlist
    @endpoints.method(WISHLIST_GET_REQUEST, BooleanMessage,
            path='session/{sessionKey}',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to Wishlist."""
        return self._sessionWishlistRegistration(request)
        
    
    # Delete session from Wishlist 
    @endpoints.method(WISHLIST_GET_REQUEST, BooleanMessage,
            path='session/{sessionKey}',
            http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """Remove session from Wishlist."""
        return self._sessionWishlistRegistration(request, reg=False)    


    # Get list of Sessions in Wishlist
    @endpoints.method(message_types.VoidMessage, SessionForms, 
        path='sessions/wishlist',
        http_method="GET", name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Get list of sessions in wishlist."""
        prof = self._getProfileFromUser() # get user Profile
        
        session_keys = [ndb.Key(urlsafe=wsck) for wsck 
        in prof.sessionKeysForWishlist]
        
        sessions = ndb.get_multi(session_keys)
        
        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )    
    
    
    # Get sessions that are 30 min in length
    @endpoints.method(message_types.VoidMessage, SessionForms, 
        path='sessions/shortSessions',
        http_method="GET", name='getShortSessions')
    def getShortSessions(self, request):
        """Get list of short (30 min or less) sessions."""
        prof = self._getProfileFromUser() # get user Profile
        
        sessionLength = 30
        sessions = Session.query(Session.duration <= sessionLength).filter(Session.duration != None)
        
        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )  

    
    # Get conferences that contain Android in the name
    @endpoints.method(message_types.VoidMessage, ConferenceForms, 
        path='conferences/keyword',
        http_method="GET", name='getConferencesByKeyword')
    def getConferencesByKeyword(self, request):
        """Get list of conferences by keyword."""
        prof = self._getProfileFromUser() # get user Profile
        
        # TODO: Update to enable wildcard like matching functionality
        # TODO: Use ComputedProperty to make query case insenstive, 
        # https://cloud.google.com/appengine/docs/python/ndb/properties#computed
        keyword = 'Android'
        conferences = Conference.query(Conference.name == keyword)
        
        # return set of ConferenceForm objects
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") for conf 
            in conferences]
        )  
    
    
    # Get sessions that start before 7:00pm and are not workshops
    @endpoints.method(message_types.VoidMessage, SessionForms, 
        path='sessions/getMySessionsOfInterest',
        http_method="GET", name='getMySessionsOfInterest')
    def getMySessionsOfInterest(self, request):
        """Get sessions that start before 7pm and are not workshops."""
        prof = self._getProfileFromUser() # get user Profile
        
        # Get sessions that are not workshops
        sessionsTypesToAvoid = 'workshop'
        sessions = Session.query(Session.typeOfSession != sessionsTypesToAvoid)
        
        # Find non-workshop sessions that start before 7:00 pm
        mySessionsOfInterest = []
        sessionCutOff = '19:00:00'
        # Convert to datetime.time
        sessionCutOffTime = datetime.strptime(sessionCutOff, "%H:%M:%S").time()
        
        for session in sessions:
            if(session.startTime <= sessionCutOffTime):
                mySessionsOfInterest.append(session)
        
        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session 
            in mySessionsOfInterest]
        )  



# - - - Profile objects - - - - - - - - - - - - - - - - - - -
    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, 
                        getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    # Get user profile
    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    # Save user profile
    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    # Get conferences you are registered for
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, 
            names[conf.organizerUserId]) for conf in conferences]
        )


    # Register for conference - update registration status
    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    # Unregister from conference - update registration status
    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


    # Endpoint to test using filters in queries
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground - test using filters in queries."""
        q = Conference.query()
        q = q.filter(Conference.city=="London")
        q = q.filter(Conference.topics=="Medical Innovations")
        q = q.filter(Conference.month==6)

        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") for conf in q]
        )


api = endpoints.api_server([ConferenceApi]) # register API
