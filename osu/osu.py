import aiohttp
from collections import namedtuple
import asyncio

from enum import Enum

from functools import reduce


class APIError(Exception):
    pass


class ArgumentError(APIError):
    def __init__(self, name, value, condition):
        super().__init__(f'{name} ! {value} : {condition}')


class _MaskNumber(Enum):
    def __new__(cls):
        if len(cls.__members__) == 0:
            value = 0
        else:
            value = 1 << (len(cls.__members__) - 1)
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


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


class Beatmap:
    '''Represents a beatmap, *not a beatmap set*. Meant to be subclassed'''
    APPROVED_STATUS = {'4': 'Loved',
                       '3': 'Qualified',
                       '2': 'Approved',
                       '1': 'Ranked',
                       '0': 'Pending',
                       '-1': 'WIP',
                       '-2': 'Graveyard'}

    GENRE_NAMES = ['Any', 'Unspecified', 'Video Game', 'Anime', 'Rock', 'Pop', 'Other',
                   'Novelty', 'If you see this message Dullvampire#0524', 'Hip Hop', 'Electronic']

    LANGUAGE_NAMES = ['Any', 'Other', 'English', 'Japanese',
                      'Chinese', 'Instrumental', 'Korean',
                      'French', 'German', 'Swedish', 'Spanish',
                      'Italian']

    MODES = ['Standard', 'Taiko', 'CtB', 'Mania']

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

        self.approved = self.APPROVED_STATUS[approved]
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

        self.genre_id = int(genre_id)
        self.genre = self.GENRE_NAMES[self.genre_id]

        self.language_id = int(language_id)
        self.language = self.LANGUAGE_NAMES[self.language_id]

        self.title = title

        self.versionName = version

        self._md5 = file_md5

        self.mode_id = int(mode)
        self.mode = self.MODES[int(mode)]

        self.tags = list(tags.split(' '))

        self.favorites = int(favourite_count)

        self.playcount = int(playcount)
        self.passcount = int(passcount)

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

        self.beatmap_id = beatmap_id
        self.beatmapset_id = beatmapset_id

        self.date = date

        self.epicFactor = int(epicfactor)


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
        self.countryRank = pp_country_rank

        self.events = [self.osuAPI.eventCls(self.osuAPI, **e) for e in events]

    def __repr__(self):
        return f'{self.username} ({self.ID})'


class Score:
    pass


class OsuAPI:
    '''API client to interact with the osu! API. Not meant to be subclassed'''

    def __init__(self, session, key, *, beatmapCls=Beatmap, userCls=User, difficultyCls=Difficulty, eventCls=Event):
        self.session = session
        self.key = key

        self.beatmapCls = beatmapCls
        self.userCls = userCls
        self.difficultyCls = difficultyCls
        self.eventCls = eventCls

    async def _APICall(self, path, parameters):
        url = 'https://osu.ppy.sh/api/' + path

        parameters.update({'k': self.key})

        async with self.session.get(url, params=parameters) as resp:
            j = await resp.json()

            if 'error' in j:
                raise APIError(f'error: {path}: {j["error"]}')

            return j

    async def getBeatmaps(self, since=None, beatmapset=None, beatmap=None, user=None, IDMode=None,
                          mode=None, includeConverted=False, bmHash=None, limit=500):
        args = {}
        if since is not None:
            args['since'] = since.strftime('%Y-%m-%d')
        if beatmapset is not None:
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
            args['mode'] = mode

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

    async def getUser(self, user, mode=0, IDMode=None, eventDays=1):
        if isinstance(user, User):
            user = user.ID
            IDMode = 'id'

        args = {'u': user}

        if mode in {0, 1, 2, 3}:
            args['m'] = mode
        else:
            raise ArgumentError('mode', mode, 'Integer[0, 3]')

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

        if mode in {0, 1, 2, 3}:
            args['m'] = mode
        else:
            raise ArgumentError('mode', mode, 'Integer[0, 3]')

        if mods is not None:
            if isinstance(mods, Mods):
                mods = mods.value
            args['mods'] = str(mods)

        if limit < 1 or limit > 500 or int(limit) - limit != 0:
            raise ArgumentError('limit', limit, 'Integer[1-500]')

        args['limit'] = limit
        print(args)

        scores = await self._APICall('get_scores', args)

        return scores


if __name__ == '__main__':
    async def main():
        with open('testingKey.txt', 'r') as f:
            KEY = f.read()
        async with aiohttp.ClientSession() as sess:
            api = OsuAPI(sess, KEY)

            user = await api.getUser(user='Dullvampire')

            print(user)

            scores = await api.getScores(917817)

            print(scores)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
