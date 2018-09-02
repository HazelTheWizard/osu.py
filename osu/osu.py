import aiohttp
from collections import namedtuple
import asyncio

from enum import Enum

from functools import reduce

from datetime import datetime

import logging

from sys import stdout

from time import monotonic, time

import json


def _toBase62(i):
    '''Unused in favor of hex'''
    encoding = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    if i == 0:
        return '0'

    if i < 0:
        raise ValueError('Must be positive')

    indices = []
    while i > 0:
        indices.append(i % 62)
        i //= 62

    return ''.join(map(lambda j: encoding[j], reversed(indices)))


class APIError(Exception):
    pass


class ArgumentError(APIError):
    def __init__(self, name, value, condition):
        super().__init__(f'{name} ! {value} : {condition}')


class ModValues(Enum):
    NONE = 0
    NO_FAIL = 1
    EASY = 2
    TOUCH_DEVICE = 4
    HIDDEN = 8
    HARD_ROCK = 16
    SUDDEN_DEATH = 32
    DOUBLE_TIME = 64
    RELAX = 128
    HALF_TIME = 256
    NIGHTCORE = 512
    FLASHLIGHT = 1024
    AUTOPLAY = 2048
    SPUN_OUT = 4096
    AUTOPILOT = 8192
    PERFECT = 16384
    KEY4 = 32768
    KEY5 = 65536
    KEY6 = 131072
    KEY7 = 262144
    KEY8 = 524288
    FADE_IN = 1048576
    RANDOM = 2097152
    CINEMA = 4194304
    TARGET = 8388608
    KEY9 = 16777216
    KEY_COOP = 33554432
    KEY1 = 67108864
    KEY3 = 134217728
    KEY2 = 268435456
    SCORE_V2 = 536870912
    LAST_MOD = 1073741824

    # Aliases
    RELAX2 = AUTOPILOT

    NF = NO_FAIL
    EZ = EASY
    HD = HIDDEN
    HR = HARD_ROCK
    SD = SUDDEN_DEATH
    DT = DOUBLE_TIME
    RX = RELAX
    HT = HALF_TIME
    NC = NIGHTCORE
    FL = FLASHLIGHT
    SO = SPUN_OUT
    AP = RELAX2
    PF = PERFECT

    NO_MOD = NONE


class Modes(Enum):
    standard = 0
    taiko = 1
    ctb = 2
    mania = 3


class LanguageNames(Enum):
    Any = 0
    Other = 1
    Enligh = 2
    Japanese = 3
    Chinese = 4
    Instrumental = 5
    Korean = 6
    French = 7
    German = 8
    Swedish = 9
    Spanish = 10
    Italian = 11


class Genres(Enum):
    Any = 0
    Unspecified = 1
    VideoGame = 2
    Anime = 3
    Rock = 4
    Pop = 5
    Other = 6
    Novelty = 7
    ERROR_CONTACT_DEVELOPER = 8
    HipHop = 9
    Electronic = 10


class ApprovedStatus(Enum):
    Loved = 4
    Qualified = 3
    Approved = 2
    Ranked = 1
    Pending = 0
    WIP = -1
    Graveyard = -2


class Mods:
    def __init__(self, *modValues):
        self.value = reduce(lambda a, b: Mods.getValue(a) | Mods.getValue(b), modValues, 0)

    @staticmethod
    def fromValue(v):
        m = Mods()
        m.value = v
        return m

    def __add__(self, o):
        if isinstance(o, Mods):
            return Mods(*self, *o)
        elif isinstance(o, ModValues):
            return Mods.fromValue(self.value | o.value)
        return NotImplemented

    def __sub__(self, o):
        if isinstance(o, Mods):
            return reduce(lambda m, v: m - v, o, Mods())
        elif isinstance(o, ModValues):
            if o not in self:
                raise ValueError(f'{str(self)} does not contain {o.name}')
            return Mods.fromValue(self.value ^ o.value)
        return NotImplemented

    def __contains__(self, o):
        if isinstance(o, ModValues):
            return self.value & o.value > 0
        return False

    def __str__(self):
        return f'({", ".join(map(lambda x: x.name, self.modList))})'

    @property
    def modList(self):
        if self.value == 0:
            return [ModValues.NONE]

        mods = []
        for i in ModValues:
            if self.value & i.value > 0:
                mods.append(i)

        return mods

    def __iter__(self):
        return iter(self.modList)

    @staticmethod
    def getValue(o):
        if isinstance(o, ModValues):
            return o.value
        return o


class Difficulty(namedtuple('Difficulty', ['bpm', 'stars', 'cs', 'od', 'ar', 'hp', 'length', 'drain', 'maxcombo'])):
    '''More understandable form of representation of difficulty. Meant to be subclassed'''
    pass


class Beatmapset:
    def __init__(self, osuAPI,
                 beatmapsetID):
        self.osuAPI = osuAPI

        self.beatmapsetID = beatmapsetID

        self.beatmapSetURL = f'https://osu.ppy.sh/s/{self.beatmapsetID}'

        self._beatmaps = None

    @property
    def beatmaps(self):
        '''Returns the list of beatmaps in non-async method. **Can return `None`**'''
        return self._beatmaps

    async def getBeatmaps(self):
        if self._beatmaps is None:
            self._beatmaps = await self.osuAPI.getBeatmaps(beatmapset_id=self.beatmapsetID)

        return self._beatmaps


class Beatmap:
    '''Represents a beatmap, *not a beatmap set*. Meant to be subclassed'''
    # APPROVED_STATUS = {'4': 'Loved',
    #                    '3': 'Qualified',
    #                    '2': 'Approved',
    #                    '1': 'Ranked',
    #                    '0': 'Pending',
    #                    '-1': 'WIP',
    #                    '-2': 'Graveyard'}
    #
    # GENRE_NAMES = ['Any', 'Unspecified', 'Video Game', 'Anime', 'Rock', 'Pop', 'Other',
    #                'Novelty', 'If you see this message Dullvampire#0524', 'Hip Hop', 'Electronic']
    #
    # LANGUAGE_NAMES = ['Any', 'Other', 'English', 'Japanese',
    #                   'Chinese', 'Instrumental', 'Korean',
    #                   'French', 'German', 'Swedish', 'Spanish',
    #                   'Italian']
    #
    # MODES = ['Standard', 'Taiko', 'CtB', 'Mania']

    def __init__(self, osuAPI,
                 approved,
                 approved_date,
                 last_update,
                 artist,
                 beatmap_id,
                 beatmapset_id,
                 bpm,
                 creator,
                 creator_id,
                 difficultyrating,
                 diff_size,
                 diff_overall,
                 diff_approach,
                 diff_drain,
                 hit_length,
                 source,  # NO IDEA WHAT THIS IS
                 genre_id,
                 language_id,
                 title,
                 total_length,
                 version,
                 file_md5,
                 mode,
                 tags,
                 favourite_count,
                 playcount,
                 passcount,
                 max_combo):
        self.api = osuAPI

        self.beatmapSet = self.api.beatmapsetCls(self.api, beatmapset_id)

        self.approved = ApprovedStatus(approved)
        self.approved_date = approved_date
        self.last_update = last_update
        self.artist = artist
        self.beatmapID = beatmap_id
        self.beatmapsetID = beatmapset_id

        self.difficulty = self.api.difficultyCls(bpm, difficultyrating, diff_size, diff_overall,
                                                 diff_approach, diff_drain, total_length, hit_length, max_combo)

        self.creator = creator
        self.creatorID = creator_id
        self.source = source

        self._creator = None

        self.genre_id = int(genre_id)
        self.genre = Genres(self.genre_id)

        self.language_id = int(language_id)
        self.language = LanguageNames(self.language_id)

        self.title = title

        self.versionName = version

        self._md5 = file_md5

        self.mode_id = int(mode)
        self.mode = Modes(int(mode))

        self.tags = list(tags.split(' '))

        self.favorites = int(favourite_count)

        self.playcount = int(playcount)
        self.passcount = int(passcount)

        self.osuDirectLink = f'osu://dl/{self.beatmapsetID}'
        self.beatmapURL = f'https://osu.ppy.sh/b/{self.beatmapID}'
        self.beatmapSetURL = self.beatmapSet.beatmapSetURL

    @property
    def creator(self):
        '''Returns the creator of the beatmap in non-async method. **Can return `None`**'''
        return self._creator

    async def getCreator(self):
        if self._creator is None:
            self._creator = self.api.getUser(self.creatorID, IDMode='id')

        return self._creator

    def __repr__(self):
        return f'{self.title} ({self.beatmap_id}/{self.beatmapset_id})'


class Event:
    '''Represents an "event". Meant to be subclassed'''

    def __init__(self, osuAPI,
                 display_html,
                 beatmap_id,
                 beatmapset_id,
                 date,
                 epicfactor):
        self.osuAPI = osuAPI

        self.displayHTML = display_html

        self.beatmapID = beatmap_id
        self.beatmapsetID = beatmapset_id

        self.beatmapSet = self.api.beatmapsetCls(self.api, beatmapset_id)

        self.date = date

        self.epicFactor = int(epicfactor)

        self._beatmap = None

    @property
    def beatmap(self):
        '''Returns the beatmap related to the event in non-async method. **Can return `None`**'''
        return self._beatmap

    async def getBeatmap(self):
        if self._beatmap is None:
            self._beatmap = (await self.osuAPI.getBeatmaps(beatmap_id=self.beatmapID))[0]

        return self._beatmap


class User:
    '''Represents a user. Meant to be subclassed'''

    def __init__(self, osuAPI,
                 user_id,
                 username,
                 count300,
                 count100,
                 count50,
                 playcount,
                 ranked_score,
                 total_score,
                 pp_rank,
                 level,
                 pp_raw,
                 accuracy,
                 count_rank_ss,
                 count_rank_ssh,
                 count_rank_s,
                 count_rank_sh,
                 count_rank_a,
                 country,
                 pp_country_rank,
                 events):
        self.osuAPI = osuAPI

        self.ID = int(user_id)
        self.username = username

        self.hitCounts = {'50': int(count50),
                          '100': int(count100),
                          '300': int(count300)}

        self.playcount = playcount

        self.rankedScore = ranked_score
        self.totalScore = total_score

        self.level = float(level)

        self.rank = int(pp_rank)
        self.pp = float(pp_raw)

        self.accuracy = float(accuracy) / 100
        self.rankCounts = {'ss': int(count_rank_ss),
                           'ssh': int(count_rank_ssh),
                           's': int(count_rank_s),
                           'sh': int(count_rank_sh),
                           'a': int(count_rank_a)}

        self.country = country
        self.countryRank = int(pp_country_rank)

        self.events = [self.osuAPI.eventCls(self.osuAPI, **e) for e in events]

        self.spectateURL = f'osu://spectate/{self.ID}'
        self.profileURL = f'https://osu.ppy.sh/u/{self.id}'

    def __repr__(self):
        return f'{self.username} ({self.ID})'


class Score:
    def __init__(self, osuAPI,
                 score,
                 count300,
                 count100,
                 count50,
                 countmiss,
                 maxcombo,
                 countkatu,
                 countgeki,
                 perfect,
                 enabled_mods,
                 user_id,
                 date,
                 rank,
                 pp=None,
                 replay_available=None,
                 username=None,
                 score_id=None,
                 beatmap_id=None):
        self.osuAPI = osuAPI

        self.IDs = {'score': score_id, 'beatmap': beatmap_id}

        nones = sum(map(lambda a: a is None, self.scores.values()))

        if nones == 0:
            self.idType = 'none'
        elif nones == 1:
            if self.scores['score'] is not None:
                self.idType = 'score'
            else:
                self.idType = 'beatmap'
        elif nones == 2:
            self.idType = 'both'

        if score_id is not None:
            self.ID = score_id
            self.IDType = 'score'
        if beatmap_id is not None:
            self.ID = beatmap_id
            self.IDType = 'beatmap'

        self.score = int(score)

        self.userName = username
        self.userID = user_id

        self.hitCounts = {'miss': int(countmiss),
                          '50': int(count50),
                          '100': int(count100),
                          '300': int(count300),
                          'katu': int(countkatu),
                          'geki': int(countgeki)}

        self.maxCombo = maxcombo

        self.perfect = perfect == '1'

        self.mods = Mods.fromValue(int(enabled_mods))

        self.date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

        self.rank = rank

        self.pp = pp
        if type(pp) == str:
            self.pp = float(pp)

        self.hasReplay = replay_available == '1'

        self._user = None

        self._beatmap = None

    async def getReplay(self):
        if self.hasReplay:
            return await self.osuAPI.getReplay(self.beatmapID, self.userID)

    @property
    def user(self):
        '''Returns the User who completed the score in non-async method. **Can return `None`**'''
        return self._user

    async def getUser(self):
        if self._user is None:
            self._user = await self.osuAPI.getUser(self.userID, IDMode='id')

        return self._user

    @property
    def beatmap(self):
        '''Returns the beatmap related to the event in non-async method. **Can return `None`**'''
        return self._beatmap

    async def getBeatmap(self):
        if self.IDs['beatmap'] is None:
            return None

        if self._beatmap is None:
            self._beatmap = (await self.osuAPI.getBeatmaps(self.IDs['beatmap']))[0]

        return self._beatmap

    def __repr__(self):
        return f'Score({self.score}, {self.idType})'


class OsuAPI:
    '''API client to interact with the osu! API. Not meant to be subclassed'''

    def __init__(self, session, key, *, rate=60, logOutput=None, loggingLevel=logging.INFO,
                 beatmapCls=Beatmap, userCls=User, difficultyCls=Difficulty, eventCls=Event,
                 scoreCls=Score, beatmapsetCls=Beatmapset,
                 loop=None, limitedTaskDelay=1, callLog=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

        self.limitedTaskDelay = limitedTaskDelay

        self.logger = logging.getLogger('osu!api')
        self.logger.setLevel(logging.DEBUG)

        logFormatter = logging.Formatter('[%(name)s]%(levelname)s : %(asctime)s: %(filename)s:%(lineno)d: %(message)s', '%m-%d %H:%M:%S')

        consoleHandler = logging.StreamHandler(stdout)
        consoleHandler.setLevel(loggingLevel)
        consoleHandler.setFormatter(logFormatter)
        self.logger.addHandler(consoleHandler)

        if logOutput is not None:
            fileHandler = logging.FileHandler(logOutput, delay=True)
            fileHandler.setLevel(logging.DEBUG)
            fileHandler.setFormatter(logFormatter)
            self.logger.addHandler(fileHandler)

        if rate > 60:
            self.logger.warning(f'Using rate limiting above 60 is discouraged')

        if rate <= 0:
            self.logger.warning(f'Invalid rate limiting {rate}, setting to 1')
            rate = 1

        self.rate = rate
        self._nextRateFree = 60

        self.session = session
        self.key = key

        self.beatmapCls = beatmapCls
        self.userCls = userCls
        self.difficultyCls = difficultyCls
        self.eventCls = eventCls
        self.scoreCls = scoreCls
        self.beatmapsetCls = beatmapsetCls

        self.rateSemaphore = asyncio.Semaphore(value=rate, loop=self.loop)
        self.replaySemaphore = asyncio.Semaphore(value=10, loop=self.loop)

        self.pastCalls = set()
        self.replayCalls = set()

        self.logger.debug(f'Created API instance with key: {key} rpm: {rate}')

        self._callID = -1

        self.callLog = callLog

        if self.callLog is not None:
            try:
                with open(self.callLog, 'r') as log:
                    line = None
                    for line in log.readlines():
                        pass
                    if line is not None:
                        self._callID = int(line.split('|')[0], 16)
            except FileNotFoundError:
                with open(self.callLog, 'w') as log:
                    log.write('callID|epochTime|path|parameters|responseStatus|timeElapsed\n')

    @property
    def callID(self):
        self._callID += 1
        return self._callID

    def removeCall(self, task):
        self.pastCalls.remove(task)

    @property
    def timeUntilFree(self):
        if not self.rateSemaphore.locked():
            return 0

        return self._nextRateFree

    def removeReplayCall(self, task):
        self.replayCalls.remove(task)

    async def reserveReplay(self):
        await asyncio.sleep(10)
        self.replaySemaphore.release()

    async def reserveCall(self):
        t = monotonic()
        left = monotonic() - t
        while left >= 0:
            await asyncio.sleep(min(left, self.limitedTaskDelay))
            left = 60 - monotonic() + t
            self._nextRateFree = min(left, self._nextRateFree)
        self.rateSemaphore.release()

    async def _APICall(self, path, parameters):
        callID = hex(self.callID)[2:]
        if self.callLog is not None:
            with open(self.callLog, 'a') as log:
                escaped = '\\|'
                log.write(f'{callID}|{time()}|{path}|{json.dumps(parameters).replace("|", escaped)}')

        wroteAll = False

        try:
            if self.rateSemaphore.locked():
                self.logger.warning(f'API Call({callID}): reached rate limit, {self.timeUntilFree:.2f} seconds left')

            await self.rateSemaphore.acquire()

            timeTaken = monotonic()
            self.logger.debug(f'API Call({callID}): {path} {parameters}')

            task = self.loop.create_task(self.reserveCall())

            self.pastCalls.add(task)

            task.add_done_callback(self.removeCall)

            url = 'https://osu.ppy.sh/api/' + path

            parameters.update({'k': self.key})

            async with self.session.get(url, params=parameters) as resp:
                self.logger.debug(f'API Call({callID}): {path} completed with status code {resp.status}')
                j = await resp.json()

                timeTaken = monotonic() - timeTaken

                with open(self.callLog, 'a') as log:
                    log.write(f'|{resp.status}|{timeTaken}')

                wroteAll = True

                if 'error' in j:
                    raise APIError(f'error: {path}: {j["error"]}')

                return j
        finally:
            with open(self.callLog, 'a') as log:
                if wroteAll:
                    log.write('\n')
                else:
                    log.write('||\n')

    async def getBeatmaps(self, since=None, beatmapset=None, beatmap=None, user=None, IDMode=None,
                          mode=None, includeConverted=False, bmHash=None, limit=500):
        args = {}
        if since is not None:
            args['since'] = since.strftime('%Y-%m-%d')
        if beatmapset is not None:
            if isinstance(beatmapset, Beatmapset):
                beatmapset = beatmapset.beatmapsetID
            args['s'] = beatmapset
        if beatmap is not None:
            if isinstance(beatmap, Beatmap):
                beatmap = beatmap.beatmapID
            args['b'] = beatmap
        if user is not None:
            if isinstance(user, User):
                user = user.ID
                IDMode = 'id'
            args['u'] = user
            if IDMode is not None:
                args['type'] = IDMode
        if mode is not None:
            args['m'] = mode.value

            if str(mode) != '0':
                if includeConverted:
                    args['a'] = 1
        if bmHash is not None:
            args['h'] = bmHash

        if limit < 1 or limit > 500 or int(limit) - limit != 0:
            raise ArgumentError('limit', limit, 'Integer[1-500]')

        args['limit'] = limit

        resp = await self._APICall('get_beatmaps', args)

        bms = []

        for datum in resp:
            bms.append(self.beatmapCls(self, **datum))

        return bms

    async def getUser(self, user, mode=None, IDMode=None, eventDays=1):
        if isinstance(user, User):
            user = user.ID
            IDMode = 'id'

        args = {'u': user}

        if mode is not None:
            args['m'] = mode.value

        if IDMode in {'string', 'id', None}:
            if IDMode is not None:
                args['type'] = IDMode
        else:
            raise ArgumentError('IDMode', mode, '("string", "id", None)')

        if 1 <= eventDays <= 31 and int(eventDays) - eventDays == 0:
            args['event_days'] = eventDays
        else:
            raise ArgumentError('mode', mode, 'Integer[1, 31]')

        resp = await self._APICall('get_user', args)

        return self.userCls(self, **resp[0])

    async def getScores(self, beatmap, user=None, mode=0, mods=None, IDMode=None, limit=50):
        if isinstance(beatmap, Beatmap):
            beatmap = beatmap.beatmapID
        args = {'b': beatmap}

        if user is not None:
            if isinstance(user, User):
                user = user.ID
                IDMode = 'id'
            args['u'] = user
            if IDMode is not None:
                args['type'] = IDMode

        if mode is not None:
            args['m'] = mode.value

        if mods is not None:
            if isinstance(mods, Mods):
                mods = mods.value
            args['mods'] = str(mods)

        if limit < 1 or limit > 100 or int(limit) - limit != 0:
            raise ArgumentError('limit', limit, 'Integer[1-100]')

        args['limit'] = limit

        return [self.scoreCls(self, **s) for s in await self._APICall('get_scores', args)]

    async def getUserBest(self, user, mode=0, limit=10, IDMode=None):
        if isinstance(user, User):
            user = user.ID
            IDMode = 'id'

        args = {'u': user}

        if mode is not None:
            args['m'] = mode.value

        if limit < 1 or limit > 100 or int(limit) - limit != 0:
            raise ArgumentError('limit', limit, 'Integer[1-100]')

        args['limit'] = limit

        if IDMode is not None:
            args['type'] = IDMode

        return [self.scoreCls(self, **s) for s in await self._APICall('get_user_best', args)]

    async def getUserRecent(self, user, mode=0, limit=10, IDMode=None):
        if isinstance(user, User):
            user = user.ID
            IDMode = 'id'

        args = {'u': user}

        if mode is not None:
            args['m'] = mode.value

        if limit < 1 or limit > 50 or int(limit) - limit != 0:
            raise ArgumentError('limit', limit, 'Integer[1-100]')

        args['limit'] = limit

        if IDMode is not None:
            args['type'] = IDMode

        return [self.scoreCls(self, **s) for s in await self._APICall('get_user_recent', args)]

    async def getReplay(self, beatmap, user, mode=0):
        await self.replaySemaphore.acquire()

        task = self.loop.create_task(self.reserveReplay())

        self.pastCalls.add(task)

        task.add_done_callback(self.removeReplayCall)

        if isinstance(user, User):
            user = user.ID

        if isinstance(beatmap, Beatmap):
            beatmap = beatmap.beatmapID

        args = {'m': mode, 'b': beatmap, 'u': user}

        return (await self._APICall('get_replay', args))['content']
