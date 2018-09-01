import aiohttp
from collections import namedtuple
import asyncio


class APIError(Exception):
    pass


class ArgumentError(APIError):
    def __init__(self, name, value, condition):
        super().__init__(f'{name} ! {value} : {condition}')


class Difficulty(namedtuple('Difficulty', ['bpm', 'stars', 'cs', 'od', 'ar', 'hp', 'length', 'drain', 'maxcombo'])):
    pass


class Beatmap:
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
        self.beatmap_id = beatmap_id
        self.beatmapset_id = beatmapset_id

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

    async def getBeatmaps(self, since=None, beatmapset=None, beatmap=None, user=None, userType=None,
                          mode=None, includeConverted=False, bmHash=None, limit=500):
        args = {}
        if since is not None:
            args['since'] = since.strftime('%Y-%m-%d')
        if beatmapset is not None:
            args['s'] = beatmapset
        if beatmap is not None:
            args['b'] = beatmap
        if user is not None:
            args['u'] = user
            if userType is not None:
                args['type'] = userType
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

    async def getUser(self, userID, mode=0, IDMode=None, eventDays=1):
        args = {'u': userID}

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


if __name__ == '__main__':
    async def main():
        with open('testingKey.txt', 'r') as f:
            KEY = f.read()
        async with aiohttp.ClientSession() as sess:
            api = OsuAPI(sess, KEY)

            user = await api.getUser(userID='Dullvampire')
            print(user.username, user.ID)
            print(user.hitCounts)
            print(user.playcount)
            print(user.rankedScore)
            print(user.totalScore)
            print(user.level)
            print(user.rank)
            print(user.pp)
            print(user.accuracy)
            print(user.rankCounts)
            print(user.country)
            print(user.countryRank)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
