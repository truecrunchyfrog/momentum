'''
WARNING!
Please read this before inspecting any file further:
This is the full source code for the Momentum bot.
If you are aware of this, please don't read the source code or any other file in this project. If you however don't have any association with Momentum, feel free to read the code!
Do not directly fork or distribute the source code or other content of this project for use in another public bot, thank you!

Copyright crunchyfrog 12/2020 - 9/2021
'''


import os, discord, pymongo, time, datetime, asyncio, random, math, requests, sys
from keep_alive import keep_alive
from discord.ext import commands
from helpmenu import helpmenu
from shopitems import shopitems
import tradecards
import hangman as ohangman
from robways import robways
import whitelist
import joinmessages
import trivia
from prestigelist import prestigelist
from PIL import Image, ImageFont, ImageDraw
from deep_translator import GoogleTranslator
import settings.channels as channels
import settings.sounds as sounds
import soundcache

all_trivia_questions = []

client = pymongo.MongoClient(os.getenv("MONGODB_CLIENT"))
userdatabase = client["users"]
usercol = userdatabase["userdata"]
studycol = userdatabase["studydata"]
metadatabase = client["meta"]
loopscol = metadatabase["loops"]
temprolescol = metadatabase["temproles"]
statscol = metadatabase["stats"]
ctrcol = metadatabase["communitytrivia"]
bntcol = metadatabase["bounties"]
timcol = metadatabase["timers"]
invcol = metadatabase["invite"]
anoncol = metadatabase["anon"]
votecol = metadatabase["votes"]
starcol = metadatabase["star"]
botactivitycol = metadatabase["botactivity"]

playingtrivia = False


#user data management

#Attributes

def GetUserAttr(uid, attrname):
    return (usercol.find_one({"_id": uid}) or {}).get(attrname)

def SetUserAttr(uid, attrname, attrvalue):
    usercol.update_one({"_id": uid}, {"$set": {attrname: attrvalue}}, upsert=True)

def RemUserAttr(uid, attrname):
    usercol.update_one({"_id": uid}, {"$unset": {attrname: ""}}, upsert=True)

#Study Tokens

def GetUserTokens(uid):
    return GetUserAttr(uid, "studytokens") or 0

def AddUserTokens(uid, amount):
    if NoTokens(uid):
      return
    SetUserAttr(uid, "studytokens", GetUserTokens(uid) + amount)

def GetUserRank(uid, sort="studytokens", default=None):
    if NoTokens(uid):
      return default
    cur = usercol.find().sort([(sort, -1)])
    i = 0
    f = default
    for doc in cur:
      i += 1
      if doc["_id"] == uid:
        f = i if (doc.get(sort) or 0) >= 100 else default
        break
    return f


def NoTokens(uid):
    # method to check if the user has chosen to be excluded from leaderboard (receive no tokens)
    return True if GetUserAttr(uid, "no_tokens") else False


#Coins

def GetUserCoins(uid):
    return GetUserAttr(uid, "coins") or 0

def AddUserCoins(uid, amount):
    SetUserAttr(uid, "coins", GetUserCoins(uid) + amount)

def TakeUserCoins(uid, amount):
    newamount = GetUserCoins(uid) - amount
    if newamount < 0:
      newamount = 0
    SetUserAttr(uid, "coins", newamount)

#Leveling and xp

def GetLevelInfo(uid):
    #xp = (usercol.find_one({"_id": uid}) or {}).get("experience") or 0
    # Not sure why I did that ^
    xp = GetUserAttr(uid, "experience") or 0
    requiredxp = 0
    i = 0
    while True:
      reqxplevel = math.floor((i + 5) ** 4)
      requiredxp += reqxplevel
      if not xp >= requiredxp:
        progrxp = math.floor(xp - (requiredxp - reqxplevel))
        remainingxp = reqxplevel - progrxp
        return {"xp": xp, "level": i, "progress": progrxp, "remaining": remainingxp, "progresspercent": math.floor((progrxp / reqxplevel) * 100), "required": reqxplevel}
      i += 1

def IsGambler(uid):
    return discord.utils.get(bot.guilds[0].roles, id=731254068055638088) in bot.guilds[0].get_member(uid).roles


# Statistics database management:

def AddToStatistics(stat_id, num):
    today = str(int(time.time() / 24 / 60 / 60))
    statscol.update_one({"_id": stat_id}, {"$inc": {("data." + today): num}}, upsert=True)


AddToStatistics("bot_launch_count", 1)


#Command decorators

class NotAdmin(commands.CheckFailure):
    pass

def admin_only():
    async def check(ctx):
        if not ctx.author.id in whitelist.admins:
          raise NotAdmin()
        return True
    return commands.check(check)

class NotCasino(commands.CheckFailure):
    pass

def casino_only():
    async def check(ctx):
        if not ctx.channel.id in [channels.Casino, 804002486003171338, 783066135662428180]:
          raise NotCasino()
        return True
    return commands.check(check)

class LevelRestricted(commands.CheckFailure):
    def __init__(self, level):
        self.rlevel = level

def level_restrict(level):
    async def check(ctx):
        if GetLevelInfo(ctx.author.id)["level"] < level and not ctx.author.id in whitelist.debug:
          raise LevelRestricted(level)
        return True
    return commands.check(check)

class NotDebugger(commands.CheckFailure):
    def __init__(self, reason):
        self.reason = reason

def debugging_only(reason="Debugging"):
    async def check(ctx):
        if not ctx.author.id in whitelist.debug:
          raise NotDebugger(reason)
        return True
    return commands.check(check)





# Time string exceptions:


# when the format is invalid
class TimeString_InvalidFormat(commands.CheckFailure):
    pass

# when an item from the time string is missing a unit, e.g. "10" instead of "10m"
class TimeString_MissingUnit(commands.CheckFailure):
    pass

# when the unit provided does not exist
class TimeString_InvalidUnit(commands.CheckFailure):
    pass



levelroles = {
  "100": 718947286331162677, #mastermind
  "75": 718947256841142293, #scholar
  "50": 718947232031965185, #grind
  "25": 718947182400503840, #bookworm
  "5": 718946501069373511 #newbie
}



async def AddExperience(channel, uid, amount):
    member = bot.guilds[0].get_member(uid)
    if member.bot:
      return
    bl = GetLevelInfo(uid)["level"]
    usercol.update_one({"_id": uid}, {"$inc": {"experience": amount}}, upsert=True)
    al = GetLevelInfo(uid)["level"]
    if al > bl:
      if al >= 100:
        await NewPrestige(uid, "whatnow")
      remxp = GetLevelInfo(uid)["remaining"]
      foundrole = False
      assignedrole = None
      for levelrole in levelroles:
        if al < int(levelrole):
          continue
        if foundrole:
          if levelroles[levelrole] in member.roles:
            await member.remove_roles(levelroles[levelrole])
          continue
        if not levelroles[levelrole] in member.roles:
          await member.add_roles(levelroles[levelrole])
          foundrole = True
          assignedrole = levelroles[levelrole]
        else:
          foundrole = True
      try:
        embed = discord.Embed()
        embed.title = f"<a:nom_party:720961569730592819> Level {al}!"
        embed.description = f"<@{uid}> reached level `{al}`, congratulations!\n`{remxp:,d}` experience left to next level." + (f"\nYou got a new role: {assignedrole.mention}" if assignedrole else "")
        embed.set_thumbnail(url="https://i.pinimg.com/originals/6e/02/79/6e02795268003bb04915790aa1302f4e.gif")
        embed.colour = 0xb58517
        await channel.send(f"<@{uid}>", embed=embed)
      except:
        pass





intents = discord.Intents.all()

bot = commands.Bot(
  command_prefix=["mom ", "Mom "],
  case_insensitive=True,
  intents=intents
)

bot.remove_command("help")

def sanitize(string):
    return discord.utils.escape_markdown(string)

def GetTimeString(timeint):
    timestr = ""
    if timeint >= 365 * 24 * 60 * 60:
      yearcountfloat = timeint / 365 / 24 / 60 / 60
      yearcountfloor = math.floor(yearcountfloat)
      timestr = str(yearcountfloor) + "y"
      extracount = math.floor((yearcountfloat - yearcountfloor) * 12)
      if extracount > 0:
        timestr += " " + str(extracount) + "mo"
    elif timeint >= 30 * 24 * 60 * 60:
      monthcountfloat = timeint / 30 / 24 / 60 / 60
      monthcountfloor = math.floor(monthcountfloat)
      timestr = str(monthcountfloor) + "mo"
      extracount = math.floor((monthcountfloat - monthcountfloor) * 30)
      if extracount > 0:
        timestr += " " + str(extracount) + "d"
    elif timeint >= 24 * 60 * 60:
      daycountfloat = timeint / 24 / 60 / 60
      daycountfloor = math.floor(daycountfloat)
      timestr = str(daycountfloor) + "d"
      extracount = math.floor((daycountfloat - daycountfloor) * 24)
      if extracount > 0:
        timestr += " " + str(extracount) + "h"
    elif timeint >= 60 * 60:
      hourcountfloat = timeint / 60 / 60
      hourcountfloor = math.floor(hourcountfloat)
      timestr = str(hourcountfloor) + "h"
      extracount = math.floor((hourcountfloat - hourcountfloor) * 60)
      if extracount > 0:
        timestr += " " + str(extracount) + "m"
    elif timeint >= 60:
      minutecountfloat = timeint / 60
      minutecountfloor = math.floor(minutecountfloat)
      timestr = str(minutecountfloor) + "m"
      extracount = math.floor((minutecountfloat - minutecountfloor) * 60)
      if extracount > 0:
        timestr += " " + str(extracount) + "s"
    else:
      timestr = str(math.floor(timeint)) + "s"
    return timestr





async def RemoveExpiredRoles():
    expiredroles = temprolescol.find({"expires": {"$lt": time.time()}})
    #print("Checking for expired roles...")
    for expiredrole in expiredroles:
      temprolescol.delete_one({"_id": expiredrole["_id"]})
      print("Found expired role, removing it...")
      if bot.guilds[0].get_member(expiredrole["user"]) is not None:
        await bot.guilds[0].get_member(expiredrole["user"]).remove_roles(discord.utils.get(bot.guilds[0].roles, id=expiredrole["role"]))
        print("Removed role from user.")
      else:
        print("Tried to remove expired role from user, but they have left the server.")
    #print("Expired role check complete!")




@bot.event
async def on_ready():
    badoc = botactivitycol.find_one({"_id": 0}) or {}
    lastactive = badoc.get("lastactive")
    lastactivitymsgid = badoc.get("lastmessage")

    if None not in [lastactive, lastactivitymsgid]:
      lastactivitymsg = await bot.get_channel(channels.General).fetch_message(lastactivitymsgid)
      await lastactivitymsg.delete()
    activitybackmsg = await bot.get_channel(channels.General).send("Hi! Momentum is back up again.")
    botactivitycol.update_one({"_id": 0}, {"$set": {"lastactive": time.time(), "lastmessage": activitybackmsg.id}}, upsert=True)

    os.system("clear")
    print("Discord authentication ready")
    for i in levelroles:
      levelroles[i] = discord.utils.get(bot.guilds[0].roles, id=levelroles[i])
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="PLEASE WAIT, SETTING UP"))
    choice = "n" or input("Create missing user documents? (y/n):").lower()
    if choice == "y":
      i = 0
      fc = 0
      mc = bot.guilds[0].member_count
      cmdstart = time.time()
      timetook = 0
      for member in bot.guilds[0].members:
        i += 1
        p = int((i / mc) * 100)
        if i == 90:
          timetook = time.time() - cmdstart
        remaining = round(timetook * (mc - i) / 100)
        tl = remaining
        sym = "<" if i % 2 else ">"
        if i % 50 == 1:
          os.system("clear")
          print(f"Creating missing documents ({i}/{mc} checked, {fc} created)\n{p}% ({tl}s left)\n{sym}")
        if not member.bot and usercol.count_documents({"_id": member.id}) == 0:
          fc += 1
          usercol.insert_one({"_id": member.id})
    if choice == "y":
      cmdtook = time.time() - cmdstart
    keep_alive()
    print("\033[01m\033[32mReady\033[0m")
    await asyncio.sleep(.02)
    if choice == "y":
      print("CREATE MISSING DOCUMENTS> Took {0}s, found {1}".format(int(cmdtook), fc))
    await UpdateStatus()
    LoadTriviaQuestions()
    asyncio.get_event_loop().create_task(er_loop())
    asyncio.get_event_loop().create_task(tc_loop())
    asyncio.get_event_loop().create_task(tr_loop())
    asyncio.get_event_loop().create_task(rb_loop())
    asyncio.get_event_loop().create_task(ic_loop())
    asyncio.get_event_loop().create_task(bc_loop())
    asyncio.get_event_loop().create_task(cc_loop())
    asyncio.get_event_loop().create_task(LoadTimers())
    await CompareDatabase()

async def UpdateStatus():
    studycount = studycol.count_documents({})
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'{studycount} {"people" if studycount != 1 else "person"} study'), status=discord.Status.idle)
    #await bot.get_channel(broadcastchannels[0]).edit(name="🌼 " + f'{studycount} {"people" if studycount != 1 else "person"} studying')

async def CompareDatabase():
    print("Initializing comparison with database and actual studying members...")
    keep_members = []
    vclist = bot.guilds[0].voice_channels
    for vc in vclist:
      if not vc in channels.NotForStudying:
        for vcmember in vc.members:
          if not vcmember.bot:
            keep_members.append(vcmember.id)
    print(f"\033[33mFound {len(keep_members)} people currently studying. Comparing with database...\033[0m")
    studycount = studycol.count_documents({})
    print(f"Database has study data of {studycount} people.")
    fromdb = studycol.find()
    print("Comparing voice channel members with database...")
    for studymember in fromdb:
      if not studymember["_id"] in keep_members:
        print("Found disagreeing data for member during comparison. Ending the member's session...")
        await StopStudying(studymember["_id"])
        print("The member's session has ended.")
    print("Comparison done!")



#remove expired roles from members
async def er_loop():
    while True:
      await RemoveExpiredRoles()
      await asyncio.sleep(3 * 60)

#tax collecting
async def tc_loop():
    while True:
      await asyncio.sleep(1 * 60 * 60)
      await CollectTaxes()

#trivia
async def tr_loop():
    while True:
      await asyncio.sleep(2 * 60 * 60)
      print("Starting trivia!")
      await SummonTrivia()

#remind bumping
async def rb_loop():
    while True:
      await asyncio.sleep(3 * 60)
      await RemindDisboardBump()

#invite clearer
async def ic_loop():
    while True:
      await asyncio.sleep(12 * 60)
      await ClearExpiredInvites()

async def ClearExpiredInvites():
    dbinvites = invcol.find()
    servinv = await bot.guilds[0].invites()
    for dbinv in dbinvites:
      for sinv in servinv:
        if sinv.code == dbinv.get("code"):
          if time.time() - sinv.created_at.timestamp() > 12 * 60 * 60:
            invcol.delete_one({"_id": dbinv.get("_id")})
            await sinv.delete()
            invowner = bot.guilds[0].get_member(dbinv.get("inviteowner"))
            try:
              await invowner.send("It's been 12 hours and your invite has expired! You can create a new one with the invite command.")
            except:
              pass
            print("Deleted an invite that had expired!")

#broadcast updater
async def bc_loop():
    while True:
      await asyncio.sleep(1 * 60)
      await UpdateBroadcastTexts()

#check cam on members
async def cc_loop():
    while True:
      await asyncio.sleep(2 * 60)
      await CheckCamMembers()

async def CheckCamMembers():
    voicestates = bot.get_channel(884074578228416522).voice_states
    for voicemap in list(voicestates.items()):
      doc = studycol.find_one({"_id": voicemap[0]})
      if doc is not None:
        if not voicemap[1].self_video and time.time() - doc.get("study_begin") > 5 * 60:
          member = bot.guilds[0].get_member(voicemap[0])
          await member.move_to(None)
          try:
            await member.send("Sorry, you have been kicked from the voice channel because you have been in there for 5 minutes without turning on your camera.")
          except:
            pass
          print("Kicked " + member.name + " from the Cam On voice channel.")

async def LoadTimers():
    timers = timcol.find()
    for timer in timers:
      if timer.get("remind_at") < time.time():
        member = bot.guilds[0].get_member(timer.get("owner"))
        timelate = time.time() - timer.get("remind_at")
        timcol.delete_one({"_id": timer.get("_id")})
        await member.send(f"<:shibasad:720968473496518676> Sorry! Your timer has come a bit late...\nYou were supposed to get this `{GetTimeString(timelate)}` ago, but because Momentum was down, you did not get it." + (("\nYour message: `" + timer.get("message") + "`") if timer.get("message") != None else ""))
      else:
        asyncio.get_event_loop().create_task(CreateTimer(timer))

existingtimers = []

async def CreateTimer(timerdoc):
    if timerdoc.get("_id") in existingtimers:
      return
    existingtimers.append(timerdoc.get("_id"))
    await asyncio.sleep(timerdoc.get("remind_at") - time.time())
    if timcol.count_documents({"_id": timerdoc.get("_id")}) == 0:
      return
    timcol.delete_one({"_id": timerdoc.get("_id")})
    member = bot.guilds[0].get_member(timerdoc.get("owner"))
    await member.send("<a:doge_dance:728195752123433030> Your timer has been reached!" + (("\n`" + timerdoc.get("message") + "`") if timerdoc.get("message") != None else "") + f"\n(Timer was `" + GetTimeString(timerdoc.get("totaltimer")) + "`)")

async def UpdateBroadcastTexts(force=False):
    if datetime.datetime.now().minute % 5 == 0 or force:
      sunmoonemoji = ""
      hour = datetime.datetime.now().hour
      if hour <= 4:
        sunmoonemoji = "☀️"
      elif hour <= 12:
        sunmoonemoji = "🌤️"
      elif hour <= 18:
        sunmoonemoji = "🌞"
      elif hour <= 20:
        sunmoonemoji = "🌘"
      elif hour <= 23:
        sunmoonemoji = "🌙"
      datetimestr = datetime.datetime.now().strftime(f"%H:%M {sunmoonemoji} %d/%m/%Y")
      await bot.get_channel(channels.Broadcasting[0]).edit(name=datetimestr)
      studyingpeople = studycol.count_documents({})
      await bot.get_channel(channels.Broadcasting[1]).edit(name=f'{"📚" if studyingpeople > 0 else "💀"} {studyingpeople} people {"are" if studyingpeople != 1 else "is"} studying')

def LoadTriviaQuestions():
    #don't update the trivia array if a game is playing. updating it during the trivia game will confuse the trivia and bugs could occur (very small chance, but still)
    if playingtrivia:
      return
    global all_trivia_questions
    all_trivia_questions = trivia.questions
    for d in ctrcol.find():
      all_trivia_questions.append([
        d.get("question"), # question
        d.get("answer"), # answer
        d.get("difficulty"), # difficulty
        d.get("genre"), # genre
        d.get("author") # trivia author id
      ])



async def SummonTrivia(channel=829389041623105616, questions=5, delay=60):
    channel = bot.get_channel(channel)
    global playingtrivia
    if playingtrivia:
      await channel.send("<a:download1:745404052598423635> Tried to start a game of trivia, but there is already one right now.")
      return
    if questions > 50:
      await channel.send("Cannot start trivia with more than 50 questions.")
      return
    if questions < 1:
      await channel.send("Cannot start trivia with less than 1 question.")
      return
    if delay > 5 * 60:
      await channel.send("Cannot set trivia delay to higher than 5 minutes.")
      return
    playingtrivia = True
    #triviarole = discord.utils.get(bot.guilds[0].roles, id=836660898302132254)
    lmsg = await channel.send("Initializing...")
    lstr = ""
    for i in range(delay):
      timeleft = delay - i + 1
      cstr = GetTimeString(timeleft)
      if i % 5 == 1 and not cstr == lstr:
        lstr = cstr
        asyncio.get_event_loop().create_task(lmsg.edit(content="",
        embed=discord.Embed(
          title=f"Game of Trivia: Starting in {cstr}",
          description=f"\n<a:CS_Wiggle:856616923915878411> Playing with **{questions}** questions.\n*How to play: There will be a few questions shown here, type the answer to the question when they occur. Your first message will count as your answer and be deleted to not show others what you typed. Later messages will not be deleted, to allow you to continue sending messages.*\n**Please read the following before playing:**\n• Do not cheat by searching for the answer or by looking at what other people are typing.\n• Let the other members guess too; don't give them the answer.\n• Do not send many messages to make the trivia message harder to see.",
          colour=0xd88e58
          )))
      await asyncio.sleep(1)
    await lmsg.delete()
    totalresults = {}
    usedqs = []
    def randomqs(am=0):
      if am >= 750:
        return None
      attempt = random.randint(0, len(all_trivia_questions) - 1)
      return attempt if not attempt in usedqs else randomqs(am + 1)
    qc = questions
    for i in range(qc):
      randidx = randomqs()
      if randidx == None:
        await channel.send("Oh no! Ran out of questions or could not load unused random question after 750 attempts...")
        break
      question = trivia.questions[randidx]
      usedqs.append(randidx)
      # Question, array;
      # 0 - Question string (with "?" or "..." etc.)
      # 1 - Answer (lowercase, cannot contain "-" etc.)
      # 2 - Difficulty (0-3, easy-hard)
      # 3 - Genre
      embed = discord.Embed()
      embed.set_author(name=f"Study Fam Trivia: {i + 1} out of {qc}")
      embed.title = question[0]
      author = bot.guilds[0].get_member(question[4]) if len(question) > 4 else None
      desc = (f"[Community question by {sanitize(author.name)}](https://duckduckgo.com \"Trivia author\")\n" if len(question) > 4 else "") + f"Difficulty: `{trivia.diffs[question[2]]}`\nGenre: `{trivia.genres[question[3]]}`\n*Type the answer!*"
      embed.description = desc
      embed.colour = discord.Colour.orange()
      qmsg = await channel.send(embed=embed)
      qstart = time.time()
      answers = {}
      def check(m):
        return m.channel.id == channel.id and not m.author.id in answers and not m.author.bot and not (len(question) > 4 and question[4] == m.author.id)
      while True:
        qtimeleft = 40 - (time.time() - qstart)
        if qtimeleft < 0:
          break
        try:
          m = await bot.wait_for("message", timeout=qtimeleft, check=check)
        except asyncio.TimeoutError:
          break
        else:
          await m.delete()
          answers[m.author.id] = m.content.lower()
          embed.description = desc + f"\n\n{len(answers)} have answered..."
          asyncio.get_event_loop().create_task(qmsg.edit(embed=embed))
      correctanswers = []
      for uid in answers:
        efi = easyfy(answers[uid])
        efa = easyfy(question[1])
        if efi == efa:
          correctanswers.append(uid)
          totalresults[uid] = (totalresults[uid] + 1 if uid in totalresults else 1)
          await AddExperience(channel, uid, [40, 70, 100][question[2]])
        else:
          await AddExperience(channel, uid, 5)
      embed.description = "Answer: **`" + (question[1]) + "`**\n*" + str(len(correctanswers)) + " out of " + str(len(answers)) + " people answered correctly.*\n\n" + ("<a:nom_party:720961569730592819> **Get ready for the next question!**" if i != qc - 1 else "<:thankyou:720988612040065135> **Thank you for playing! Wait to see the results...**")
      embed.colour = discord.Colour.green()
      await qmsg.edit(embed=embed)
      await asyncio.sleep(15)
      await qmsg.delete()
      if i == qc - 1:
        embed = discord.Embed()
        embed.set_author(name="Thank you for playing some trivia!")
        embed.description = "" if len(totalresults) != 0 else "No results."
        embed.set_footer(text="This message will disappear soon.")
        for user in totalresults:
          embed.description += f"<@{user}> - `{totalresults[user]}/{qc}`\n"
        embed.colour = discord.Colour.blurple()
        rmsg = await channel.send(embed=embed)
        playingtrivia = False
        await asyncio.sleep(40)
        await rmsg.delete()




async def CollectTaxes():
    idstr = "collect_taxes"
    delay = 30 * 24 * 60 * 60
    if IsDelayedLoopReady(idstr, delay):
      UpdateLoopUsed(idstr, delay)
      print("COLLECTING TAXES! It has been >30 days since last tax collection.")
      taxpayers = usercol.find({"coins": {"$gte": 8000}})
      totalcoinstaken = 0
      for taxpayer in taxpayers:
        takecoins = int(taxpayer["coins"] * .2)
        totalcoinstaken += takecoins
        TakeUserCoins(taxpayer["_id"], takecoins)
      print("All members with >8k coins have automatically paid taxes, 20% of their full coin amount.")
      await bot.get_channel(channels.General).send(embed=discord.Embed(
        description=f"<:blobcute:720968544602554388> It's time for this month's taxes!\nCollected `{totalcoinstaken:,d} coins` in total. ([?](https://discord.com/channels/712808127539707927/713177565849845849/801373465546457138 \"Click to see more information about taxes\"))",
        colour=discord.Colour.orange()
      ))


async def RemindDisboardBump():
    idstr = "remind_bump"
    delay = 2 * 60 * 60
    if IsDelayedLoopReady(idstr, delay):
      UpdateLoopUsed(idstr, delay)
      embed = discord.Embed()
      embed.set_author(name="BUMPING AVAILABLE!")
      embed.title = "<a:CS_Wiggle:856616923915878411> Contribute to Study Fam!"
      embed.description = "Help the server grow by typing `!d bump`.\n**Due to Disboard changes (since 22 Sep.), you will no longer receive a bump reward.**"
      embed.colour = 0x2f3136
      await bot.get_channel(channels.BotCommands).send(embed=embed)


def IsDelayedLoopReady(id, delay):
    # id is the loop id used in the database, e.g. collect_taxes
    # delay is the amount of seconds for the delay to be
    doc = loopscol.find_one({"_id": id})
    if doc is None or (doc["last_used"] < time.time() - delay):
      return True
    else:
      return False


def UpdateLoopUsed(id, delay):
    loopscol.update_one({"_id": id}, {"$set": {"delay": delay, "last_used": time.time()}}, upsert=True)





@bot.event
async def on_message(message):
    if message.author.bot:
      if message.author.id == 302050872383242240 and len(message.embeds) > 0 and "Bump done" in message.embeds[0].description:
        UpdateLoopUsed("remind_bump", 2 * 60 * 60)
      return
    if isinstance(message.channel, discord.channel.DMChannel):
      return

    c = message.content
    if message.channel.id == 748862262793732160 and len(message.attachments) == 1:
      await NewPrestige(message.author.id, "nicememe")
    lc = c.lower()
    if ("sleep" in lc or "to bed" in lc) and len(c) < 40 and (("have to" in lc or "should" in lc or "will" in lc or "now" in lc or "head" in lc or "going to" in lc) and not "soon" in lc and (not "you" in lc or (" i " in lc or " i'" in lc or " im " in lc))):
      async with message.channel.typing():
        await asyncio.sleep(random.randint(4, 8))
        await message.reply(random.choice(["Sleep well {0}! We'll see you later.", "It's been a long day. You deserve a good sleep {0}!", "Well done {0}! Good night!", "Good night mate {0}!", "See you tomorrow {0}!", "Good night {0}! Sleep well!", "You have done well today, as everyday!", "Today was a big day, tomorrow is a big day. You should get some good sleep!", "We all wish you a good night {0}!"]).format(sanitize(message.author.name)))
    if "beaver" in lc and len(c) < 35:
      await message.reply("https://tenor.com/view/baby-beaver-cute-gif-9929643", delete_after=11)
    if (("mom" in lc or "beaver" in lc) and len(lc) < 80 and ("you" in lc or " u " in lc or "u'" in lc or " ur " in lc or " go " in lc) and ("work" in lc or "slave" in lc or "poor" in lc or "suck" in lc or "bad" in lc or "i hate" in lc or "terrible" in lc or "stink" in lc or "die" in lc or "ugly" in lc or "annoying" in lc)):
      await message.channel.send("You gotta do what you gotta do.")
      return
    if lc == "no regrets":
      await SelfDestruction(message)
    if message.reference is not None:
      mid = message.reference.message_id
      anondoc = anoncol.find_one({"_id": mid})
      if anondoc is not None and anondoc.get("author") != message.author.id:
        anonauthor = bot.guilds[0].get_member(anondoc.get("author"))
        try:
          await anonauthor.send(sanitize(message.author.name) + " replied to your anonymous message: " + message.jump_url)
        except:
          pass
    if message.content == f"<@!{bot.user.id}>":
      await message.channel.send("For help, type `mom help`.")
    if lc.startswith("pls ") and message.channel.id == channels.BotCommands:
      await message.reply(f"Please use Dank Memer commands in {bot.get_channel(channels.DankMemer).mention}.")
    if not lc.startswith("mom "):
      if random.randrange(0, 2) == 0:
        await AddExperience(message.channel, message.author.id, 15)
      # give study tokens for sending messages in "music study chat"
      if message.channel.id == 722880141134397460 and random.randrange(0, 2) == 0:
        AddUserTokens(message.author.id, 1)
    if message.channel.id == 725451170604384308 and not (GetUserAttr(message.author.id, "dca") or False):
      await message.delete()
      conf = await message.channel.send(message.author.mention + " You sure you wanna chat here?")
      await conf.add_reaction("👍")
      def check(reaction, user):
        return user.id == message.author.id and reaction.message.channel.id == message.channel.id and reaction.emoji == "👍"
      try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30, check=check)
      except asyncio.TimeoutError:
        await conf.delete()
        await message.channel.send("No chat for you!", delete_after=10)
      else:
        await conf.delete()
        SetUserAttr(message.author.id, "dca", True)
        await message.channel.send("Great, now you can chat here!", delete_after=10)
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):
    invitelist = invcol.find()
    servinv = await bot.guilds[0].invites()
    for inv in invitelist:
      invexists = False
      for sinv in servinv:
        if sinv.code == inv.get("code"):
          invexists = True
      if not invexists:
        invcol.delete_one({"_id": inv.get("_id")})
        inviter = bot.guilds[0].get_member(inv.get("inviteowner"))
        memberinvlist = GetUserAttr(inviter.id, "invite_list") or []
        if inviter.id == member.id:
          await inviter.send("Uhm..? You invited yourself? This won't work. Good attempt though.")
          continue
        if member.id in memberinvlist:
          await inviter.send("Hey! Sorry, but the person you invited has already been invited by you! Please reuse the invite command and give it to someone else instead.")
          continue
        memberinvlist.append(member.id)
        SetUserAttr(inviter.id, "invite_list", memberinvlist)
        AddUserCoins(inviter.id, 2000)
        try:
          await inviter.send("Thank you for inviting " + sanitize(member.name) + " to Study Fam! You have been given <:famcoin2:845382244554113064> `2,000`.")
        except:
          pass
        # don't break the loop here, to allow previous invites to be cleared as well, if they were removed while the bot was offline
    print(member.name + " joined the server!")
    embed = discord.Embed()
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{member.id}/{member.avatar}.png?size=64")
    embed.description = f"\n{random.choice(joinmessages.emojis)} " + (random.choice(joinmessages.messages).format(f"[{sanitize(member.name)}#{member.discriminator}](https://discord.com/channels/@me/{member.id} \"That's great!\")"))
    embed.colour = 0x2f3136
    await bot.get_channel(channels.General).send(embed=embed, delete_after=5 * 60)

@bot.event
async def on_raw_reaction_add(payload):
    if votecol.count_documents({"message": payload.message_id, "active": True}) > 0 and payload.member.id != bot.user.id:
      # Someone reacted to a message which is a vote
      message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
      await message.remove_reaction(payload.emoji, payload.member)
      votetypes = ["👍", "👎", "✅"]
      if payload.emoji.name in votetypes:
        index = votetypes.index(payload.emoji.name)
        doc = votecol.find_one({"message": message.id})
        if index < 2:
          if doc.get("author") != payload.member.id:
            nvd = doc.get("votes")
            nvd["?" + str(payload.member.id)] = index
            votecol.update_one({"message": payload.message_id}, {
              "$set": {"votes": nvd}
            })
          else:
            await message.channel.send(payload.member.mention + " You cannot participate in your own vote!", delete_after=5)
            return
        else:
          # Close vote
          if doc.get("author") == payload.member.id or payload.member.id in whitelist.admins:
            votecol.update_one({"message": message.id}, {"$set": {"active": False, "ended": time.time()}})
            # Remove all the reactions:
            for reaction in message.reactions:
              for user in await reaction.users().flatten():
                await reaction.remove(user)
          else:
            await message.channel.send(payload.member.mention + " You don't have the permission to end this vote!", delete_after=5)
        await UpdateVoteMessage(message)
    if payload.emoji.id == 889981889828511794:
      # Someone reacted with the "star"-ing emoji
      message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
      await message.remove_reaction(payload.emoji, payload.member)
      if payload.member.id == message.author.id:
        try:
          await payload.member.send("You cannot star your own messages.")
        except:
          pass
        return
      starcost = 300
      try:
        await payload.member.send(embed=discord.Embed(
          title="<:0_momentum_star:889981889828511794> Star this message?",
          description=f"Do you want to pay <:famcoin2:845382244554113064> `{starcost}` coins to star [{sanitize(message.author.name)}'s message]({message.jump_url})?\nTheir message will display in {bot.get_channel(channels.BeaverBoard).mention}.\nType `yes` to confirm and place the message there.",
          colour=0x721806
        ))
      except:
        return
      def check(m):
        return m.author.id == payload.member.id and m.channel == payload.member.dm_channel
      try:
        m = await bot.wait_for("message", timeout=60, check=check)
      except asyncio.TimeoutError:
        return
      else:
        if m.content.lower() == "yes":
          if GetUserCoins(payload.member.id) >= starcost:
            if starcol.count_documents({"_id": message.id}) == 0:
              TakeUserCoins(payload.member.id, starcost)
              starcol.insert_one({"_id": message.id})
              embed = discord.Embed()
              embed.set_author(name=message.author.name, icon_url=message.author.avatar_url_as(size=32))
              sendfiles = []
              if len(message.attachments) == 0:
                embed.description = message.content or "..."
              else:
                for attc in message.attachments:
                  sendfiles.append(await attc.to_file())
                ac = len(message.attachments)
                embed.description = str(ac) + " attachment" + ("s" if ac != 1 else "")
              embed.description += f"\n\n[Hop to the source]({message.jump_url}) (originally posted {GetTimeString(time.time() - message.created_at.timestamp())} ago)"
              embed.colour = 0xdd7863
              embed.set_footer(text=f"Starred by: {payload.member.name}#{payload.member.discriminator}")
              await bot.get_channel(channels.BeaverBoard).send(embed=embed, files=sendfiles)
              await payload.member.send("The message was starred!")
            else:
              await payload.member.send("That message has already been starred!")
          else:
            await payload.member.send(f"Uh oh, you don't have enough coins to star a message! It costs `{starcost}` but you only have `{GetUserCoins(payload.member.id)}` coins.")
        else:
          await payload.member.send("The message was not starred.")
    if payload.member.id == 482459199213928459:
      message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
      shouldAdd = True
      for reaction in message.reactions:
        if str(reaction.emoji) == str(payload.emoji):
          if reaction.me:
            shouldAdd = False
          break
      if shouldAdd:
        await message.add_reaction(payload.emoji)
      else:
        await message.remove_reaction(payload.emoji, bot.user)
      await message.remove_reaction(payload.emoji, payload.member)


lasterror = 0

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("Expected a member.")
    elif isinstance(error, commands.CommandNotFound):
      await ctx.send(embed=discord.Embed(
        description=f"<a:thisisfine:856617800395259904> Sorry! No such command: [`{sanitize(ctx.invoked_with)}`](https://duckduckgo.com) could be found.\nRun `mom help` and see if you can find what you are looking for.\nYou can also ask staff to help you find it.",
        colour=0x2f3136
      ))
    elif isinstance(error, NotAdmin):
      await ctx.send("<:shibashock:720967877410160732> Only administrators, the owner or the developer can do this.")
    elif isinstance(error, NotCasino):
      await ctx.send("<a:download1:745404052598423635> You must be in the casino channel to do this!\nYou may have to unlock it in the shop.")
    elif isinstance(error, LevelRestricted):
      await ctx.send(f"<:shibaplease:720961487103066224> You need to be level **{error.rlevel}** to do this.")
    #Time string errors
    elif isinstance(error, TimeString_InvalidFormat):
      await ctx.send("<:facepalm:739540188136734797> **Invalid time format!**\nExample usage: `1h 45m 30s`")
    elif isinstance(error, TimeString_MissingUnit):
      await ctx.send("<:facepalm:739540188136734797> **Missing time unit!**\nYou did not type the unit.\nUse `15m 30s`, not `15 30`.")
    elif isinstance(error, TimeString_InvalidUnit):
      await ctx.send("<:facepalm:739540188136734797> **Invalid unit!**\nYou used a time unit that doesn't exist.\nThe valid units are:\n• `w` (weeks)\n• `d` (days)\n• `h` (hours)\n• `m` (minutes)\n• `s` (seconds)")
    elif isinstance(error, NotDebugger):
      await ctx.send(f"<:shibasad:720968473496518676> Sorry! This command cannot be used at the moment.\nReason: `{error.reason}`")
    elif isinstance(error, commands.ExpectedClosingQuoteError):
      await ctx.send("Your command had a quote that did not close and it has not been executed. Please fix it and try again.")
    else:
      #unknown error
      global lasterror
      if (time.time() - lasterror) < 2:
        embed = discord.Embed()
        embed.description = "**WARNING!**\nMultiple errors occured with little delay.\nShutting down Momentum to prevent bad things..."
        embed.colour = 0x2f3136
        embed.set_thumbnail(url="attachment://broken.png")
        file = discord.File("images/icons/broken_robot.png", filename="broken.png")
        await ctx.send(file=file, embed=embed)
        print("Shutting down bot because of too many errors")
        sys.exit()
      lasterror = time.time()
      embed = discord.Embed()
      embed.description = f"<a:thisisfine:856617800395259904> Sorry, {sanitize(ctx.author.name)}!\nAn error occured while trying to run your command: `{sanitize(ctx.invoked_with)}`.\nPing the developer by clicking the check icon below.\n**Debug information:**\n```\n{error}```"
      embed.colour = 0x2f3136
      embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/861542071905943562/890874808412291092/image.png")
      emsg = await ctx.send(embed=embed)
      await emsg.add_reaction("<:Check:783760461556350986>")
      def check(reaction, user):
        return user.id == ctx.author.id and reaction.message.id == emsg.id and reaction.emoji.id == 783760461556350986
      try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
      except asyncio.TimeoutError:
        await emsg.remove_reaction("<:Check:783760461556350986>")
      else:
        await emsg.clear_reaction("<:Check:783760461556350986>")
        await emsg.remove_reaction("<:Check:783760461556350986>", ctx.author)
        await emsg.reply("<@&829737618018140180>")
      raise error


@bot.event
async def on_voice_state_update(member, before, after):
    using_cam = False
    if member.voice and (member.voice.self_stream or member.voice.self_video):
      using_cam = True
    # Start studying
    if (not before.channel or before.channel.id in channels.NotForStudying) and after.channel and studycol.find_one({"_id": member.id}) is None and not after.channel.id in channels.NotForStudying and not member.bot:
      if len(after.channel.members) >= 11: # 11 because this member is included into the count as well
        await NewPrestige(member.id, "studyarmy")
      studycol.insert_one({"_id": member.id, "study_begin": time.time(), "cam_usage": 0})
      await PlayJoinStudySound(member.id, after.channel)
    if studycol.find_one({"_id": member.id}) is not None and using_cam:
      studycol.update_one({"_id": member.id}, {"$set": {"cam_usage_begin": time.time()}})
    if not using_cam and studycol.find_one({"_id": member.id, "cam_usage_begin": {"$exists": True}}) is not None:
      cam_usage_begin = studycol.find_one({"_id": member.id}).get("cam_usage_begin")
      studycol.update_one({"_id": member.id}, {
        "$unset": {"cam_usage_begin": ""},
        "$inc": {"cam_usage": time.time() - cam_usage_begin}
      })
    # Stop studying
    if before.channel and (not after.channel or after.channel.id in channels.NotForStudying) and studycol.count_documents({"_id": member.id}) > 0:
      await StopStudying(member.id)
    await UpdateStatus()


async def StopStudying(member_id):
    member = bot.guilds[0].get_member(member_id)
    if member is None:
      studycol.delete_one({"_id": member_id})
      return
    studytime_elapsed = time.time() - studycol.find_one({"_id": member.id}).get("study_begin")
    cam_usage = studycol.find_one({"_id": member.id}).get("cam_usage")
    used_cam = cam_usage > (studytime_elapsed / 2)
    studycol.delete_one({"_id": member.id})
    maxtime = 6 * 60 * 60
    limitreached = False
    if studytime_elapsed > maxtime:
      studytime_elapsed = maxtime
      limitreached = True
    # Check prestiges:
    if studytime_elapsed > 2 * 60 * 60:
      await NewPrestige(member.id, "twohourstudy")
    if datetime.datetime.today().weekday() == 6:
      #sunday
      await NewPrestige(member.id, "sundaystudy")
    # End check prestiges
    silent_earnings_tokens = 5 / 60
    silent_earnings_coins = 1.8 / 60 # orig. 10 / 60
    cam_earnings_tokens = 6.5 / 60
    cam_earnings_coins = 2 / 60 # orig. 13 / 60
    earnstudytokens = round(studytime_elapsed * (silent_earnings_tokens if not used_cam else cam_earnings_tokens))
    earncoins = round(studytime_elapsed * (silent_earnings_coins if not used_cam else cam_earnings_coins))
    before_rank = GetUserRank(member.id, default="unavailable")
    AddUserTokens(member.id, earnstudytokens)
    after_rank = GetUserRank(member.id, default="unavailable")
    AddUserCoins(member.id, earncoins)
    SetUserAttr(member.id, "studytime", (GetUserAttr(member.id, "studytime") or 0) + studytime_elapsed)
    await AddExperience(member, member.id, int(studytime_elapsed))
    smmode = GetUserAttr(member.id, "studymessages")
    if smmode is None:
      smmode = True
    hasgoal = (GetUserAttr(member.id, "dailygoal") or [0, 0, 0])[2] == math.floor(time.time() / 24 / 60 / 60)
    try:
      if not smmode is False:
        embed = discord.Embed()
        embed.title = "<:1498pepestudying:841710573896335410> Study session complete!"
        embed.description = f"<:0_momentum_star:889981889828511794> Studied for `{GetTimeString(studytime_elapsed)}`" + (f"\n\n<:0_momentum_star:889981889828511794> `+{earnstudytokens:,d} study tokens` <:book:816522587424817183>" if not NoTokens(member.id) else "") + f"\n\n<:0_momentum_star:889981889828511794> `+{earncoins:,d} coins` <:famcoin2:845382244554113064>" + ("\n\n<:0_momentum_star:889981889828511794> Camera/screenshare boosted profits" if used_cam else "") + (f"\n\n<:0_momentum_star:889981889828511794> <:beaver_2:841722221671743488> Woo! Your leaderboard rank went up: [`{before_rank}`](https://duckduckgo.com \"Your previous rank\") **➝** [`{after_rank}`](https://duckduckgo.com \"Your current rank\")" if before_rank != after_rank else (f"\n\n<:0_momentum_star:889981889828511794> Your leaderboard rank is [`{after_rank}`](https://duckduckgo.com \"Your rank\")" if not NoTokens(member.id) else "")) + (f"\n\n<:6773_Alert:783760764153495582> Oh no! You studied for `{GetTimeString(studytime_elapsed)}` which exceeds the study session limit of `6h`. Your earnings and study time was shortened to 6 hours instead of how long time you actually was there." if limitreached else "") + ("\n\n<:0_momentum_star:889981889828511794> You got closer to your study goal" if hasgoal else "")
        embed.colour = discord.Colour.green()
        embed.description += "\n\n[Want to disable these messages?](https://discord.com/channels/712808127539707927/713177565849845849/796105551229616139 \"Click to see how you can prevent these messages from being sent to you\")"
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/802215570996330517/889594173861269605/momentum_session_complete.png")
        if smmode is True:
          await member.send(embed=embed)
        elif smmode == "server":
          await bot.get_channel(channels.BotCommands).send(member.mention, embed=embed)
    except:
      pass
    if hasgoal:
      goalarr = GetUserAttr(member.id, "dailygoal")
      goalarr[1] -= studytime_elapsed
      if 0 >= goalarr[1]:
        RemUserAttr(member.id, "dailygoal")
        await AddExperience(member, member.id, (goalarr[0] / 60 / 60) * 600)
        try:
          if not smmode is False:
            goalembed = discord.Embed()
            goalembed.title = "<:king_cat:730063415959224320>"
            goalembed.description = f"You reached your `{GetTimeString(goalarr[0])}` goal for today! Have some :cake:!"
            goalembed.colour = discord.Colour.gold()
            if smmode is True:
              await member.send(embed=embed)
            elif smmode == "server":
              await bot.get_channel(channels.BotCommands).send(member.mention, embed=embed)
        except:
          pass
      else:
        SetUserAttr(member.id, "dailygoal", goalarr)

async def PlayJoinStudySound(uid, channel):
    member = bot.guilds[0].get_member(uid)
    vclient = bot.guilds[0].voice_client
    if vclient is None:
      vclient = await channel.connect()
    else:
      await vclient.move_to(channel)
    await asyncio.sleep(2)
    def playSound():
      try:
        vclient.play(soundcache.GetSound(sounds.Sounds[0]))
      except:
        pass
    playSound()
    await asyncio.sleep(10)
    await vclient.disconnect()

async def UpdateVoteMessage(message):
    if votecol.count_documents({"message": message.id}) > 0:
      doc = votecol.find_one({"message": message.id})
      numvotes = len(doc.get("votes"))
      embed = discord.Embed()
      embed.set_author(name=f'Vote #{doc.get("code")} by {bot.guilds[0].get_member(doc.get("author"))}', icon_url="https://icons.iconarchive.com/icons/flameia/rabbit-xp/128/documents-icon.png")
      embed.title = doc.get("text")
      if doc.get("active"):
        embed.description = str(numvotes) + " vote" + ("s" if numvotes != 1 else "") if numvotes > 0 else "No votes yet."
        embed.set_footer(text="Participate anonymously by voting below")
      else:
        votes = doc.get("votes")
        upvotes = 0
        downvotes = 0
        for v in votes:
          if votes[v] == 0:
            upvotes += 1
          else:
            downvotes += 1
        desc = "The vote has ended!\n\n"
        if upvotes != downvotes:
          desc += "Most **" + ("upvotes" if upvotes > downvotes else "downvotes") + "**"
        else:
          desc += "**Tie**" if numvotes > 0 else "**No votes**"
        if numvotes > 0:
          desc += "\n\nUpvotes: " + str(upvotes) + " (" + str(math.floor((upvotes / numvotes) * 100)) + "%)"
          desc += "\nDownvotes: " + str(downvotes) + " (" + str(math.floor((downvotes / numvotes) * 100)) + "%)"
        embed.description = desc
      embed.colour = 0x976cb2
      await message.edit(content="", embed=embed)


@bot.command(aliases=["level", "coins", "tokens", "xp", "experience", "rank", "bank", "balance", "bal"])
async def stats(ctx, user: discord.Member=None):
    if user is None:
      user = ctx.author
    if user.bot:
      await ctx.send("That's a... bot? Bots don't have profiles. ||:(||")
      return
    embed = discord.Embed()
    embed.set_author(name=user.name)
    lvlinfo = GetLevelInfo(user.id)
    embed.set_thumbnail(url=user.avatar_url_as(size=128))
    if not NoTokens(user.id):
      embed.add_field(name="<:book:816522587424817183> Study tokens", value=f"`{GetUserTokens(user.id):,d}`")
    embed.add_field(name=(("<:famcoin2:845382244554113064> Coins" if user.id != 824316055681761320 else "<a:cat_popcorn:853734055765606430> Popcorn bank") if user.id != 577934880634306560 else "<a:1150_pugdancel:856637771795267614> Doggy bank") if user.id != 799293092209491998 else "🐖 Piggy bank", value=f"**{GetUserCoins(user.id):,d}**")
    studytime = GetUserAttr(user.id, "studytime")
    embed.add_field(name="<:pepestudying:841710573896335410> Study time", value=GetTimeString(studytime) if studytime is not None else "No study session yet!")
    if not NoTokens(user.id):
      embed.add_field(name="🧗 Rank", value="`" + str(GetUserRank(user.id, default="Unavailable")) + "`")
    prog = lvlinfo["progress"]
    req = lvlinfo["required"]
    rem = lvlinfo["remaining"]
    embed.add_field(name="<:4813bigbrain:861353869216841769> Experience", value=f"[{prog:,d}" + " / " + f"{req:,d}](https://duckduckgo.com \"{rem:,d} left\")" + " (" + str(lvlinfo["progresspercent"]) + "%)")

    #embed.add_field(name="<:beaver_2:841722221671743488> Bump contributions", value=f'{GetUserAttr(user.id, "bump_count") or "No contributions yet!"}')
    
    cardcount = len(GetUserAttr(user.id, "card_inventory") or [])
    embed.add_field(name="<:crunchys:861351443004915712> Trade cards", value=cardcount if cardcount > 0 else "No trade cards yet!")

    embed.description = "**[`  " + (" " * 11) + str(lvlinfo["level"]) + (" " * (11 - len(str(lvlinfo["level"])))) + "  `](https://duckduckgo.com \"Level\")**\n"
    BAR_ON = "<:progress_solid_on:891446235582590986>"
    BAR_OFF = "<:progress_solid_off:891446323767803934>"
    for i in range(10):
      mode = not (lvlinfo["progresspercent"] / 10) <= i
      embed.description += BAR_ON if mode else BAR_OFF
    embed.description += "\n\n[Confused by the different stats?](https://discord.com/channels/712808127539707927/713177565849845849/796415766005284874 \"Click here to see an explanation of them\")"
    if NoTokens(user.id):
      embed.description += f"\n[{sanitize(user.name)} has disabled study tokens.](https://discord.com/channels/712808127539707927/713177565849845849/807738082903457802 \"More information about disabling study tokens\")"
    if user.joined_at is not None:
      embed.description += "\n*Joined " + GetTimeString(time.time() - user.joined_at.timestamp()) + " ago*"


    col = None
    level = GetLevelInfo(user.id)["level"]
    if level >= 100:
      col = 0x59126d
    elif level >= 90:
      col = 0xeabf25
    elif level >= 75:
      col = 0x25ea8e
    elif level >= 50:
      col = 0xb925ea
    elif level >= 30:
      col = 0x5625ea
    elif level >= 20:
      col = 0xea4625
    elif level >= 10:
      col = 0x799122
    elif level >= 5:
      col = 0x22916e
    else:
      col = 0x916e22
    embed.colour = col
    await ctx.send(embed=embed)



@bot.command()
async def studymessages(ctx, mode=None):
    currentmode = GetUserAttr(ctx.author.id, "studymessages")
    if currentmode == None:
      currentmode = True
    modes = ["on", "off", "server"]
    if mode is None or mode.lower() not in modes:
      await ctx.send("Study messages are **{0}**.\nType `mom studymessages off/on/server` to disable/enable study messages.".format(["enabled", "disabled", "in server"][0 if currentmode is True else (1 if currentmode is False else (2 if currentmode == "server" else None))]))
      return
    mode = mode.lower()
    newmode = True if modes.index(mode) == 0 else (False if modes.index(mode) == 1 else "server")
    if newmode == currentmode:
      await ctx.send(f"Study messages are already set to **{mode}** for you.")
      return
    SetUserAttr(ctx.author.id, "studymessages", newmode)
    await ctx.send(f"Study messages have been set to **{mode}**.")



@bot.command(aliases=["lb"])
async def leaderboard(ctx, page=None):
    if page is None:
      #select page where they are
      rank = GetUserRank(ctx.author.id)
      if rank is None:
        page = "1"
      else:
        if int((rank + 1) / 10) < 1:
          page = "1"
        else:
          page = str(int((rank + 9) / 10))
    if page.isnumeric():
      page = int(page)
    else:
      await ctx.send(f"Page was not a number. You gave `{sanitize(page)}`.")
      return
    if page < 1:
      await ctx.send("Page cannot be less than 1.")
      return
    rquery = {
      "studytokens": {"$gte": 100}
    }
    lbdocne = usercol.find(rquery, {"_id": 1, "studytokens": 1})
    if usercol.count_documents(rquery) == 0:
      await ctx.send("Sorry, but it seems that no one can be in sight of the leaderboard yet. Just start studying and you'll get here.")
      return
    n1mem = bot.guilds[0].get_member(lbdocne.sort([("studytokens", -1)])[0].get("_id"))
    lbdoc = lbdocne.sort([("studytokens", -1)]).skip((page - 1) * 10).limit(10)
    pagecount = math.ceil(usercol.count_documents(rquery) / 10)
    embed = discord.Embed()
    embed.title = "<:book:816522587424817183> Leaderboard (Monthly rankings)"
    embed.set_thumbnail(url=n1mem.avatar_url_as(size=64))
    embed.description = ""
    ii = (page - 1) * 10
    i = ii
    for user in lbdoc:
      i += 1
      mem = bot.guilds[0].get_member(user.get("_id"))
      name = sanitize(mem.name if mem else "<User left server>")
      st = user.get("studytokens")
      embed.description += (":medal:" if i == 1 else "") + f"[`#{i}`](https://duckduckgo.com \"Rank\") **" + name + "**" + (" [**[ YOU ]**](https://duckduckgo.com \"This is you\")" if user.get("_id") == ctx.author.id else "") + "\n<:book:816522587424817183>`" + f"{st:,d}" + "`\n"
    if i == ii:
      embed.description = "Empty page."
    selfrank = GetUserRank(ctx.author.id)
    embed.description += f'\nYour leaderboard rank is [`{selfrank or "unavailable"}`](https://duckduckgo.com "{sanitize(ctx.author.name)}\'s rank")'
    if selfrank is None:
      embed.description += "\n[Why am I not shown on the leaderboard?](https://discord.com/channels/712808127539707927/713177565849845849/831853167858942012 \"Click to see why you are not shown on the leaderboard\")"
    embed.colour = 0x34133f
    embed.set_footer(text=f"Page {page}/{pagecount}")
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx, *, showcategory=None):
    embed = discord.Embed()
    if showcategory is None:
      embed.description = f"Hey!\n**Momentum** is the bot for Study Fam. I will keep track of your studying, and at the same time serve much more features to keep your stay here as great as possible.\nAll you have to do is join a voice channel and get studying!\nThese are just some of the things I serve:\n• Tracking your studying\n• Leaderboard\n• Tools, preferences and options\n**Questions? Suggestions?** [Feel free to ask us](https://discord.com/channels/712808127539707927/857739970978775040/858281583348547584 \"Click to ask a question or suggest something\") or [see common questions and answers](https://discord.com/channels/712808127539707927/713177565849845849/845653574990168065 \"Click to see a list of common questions and their answers\").\n\nType `mom help <category>` to see the commands of a category."
      for categ in helpmenu:
        embed.description += f'\n\n☞ [**{categ["name"]}**](https://duckduckgo.com \'Type "mom help {categ["name"]}" to see the commands of this category\')\n{categ.get("description") or "No description."}\n*{len(categ["commands"])} commands*'
      embed.colour = 0x4f771a
    else:
      chosencateg = None
      for category in helpmenu:
        if easyfy(category["name"]) == easyfy(showcategory):
          chosencateg = category
          break
        else:
          for alias in (category.get("aliases") or []):
            if easyfy(alias) == easyfy(showcategory):
              chosencateg = category
              break
      if chosencateg is not None:
        embed.title = chosencateg["name"]
        embed.description = (chosencateg.get("description") or "No description for category.") + "\n\n*" + str(len(chosencateg["commands"])) + " commands*\n\nUse `mom command` to run a command.\nParameters marked with `<>` are essential and `[]` parameters are optional.\nHover a command or click the spoiler to see command parameters."
        for cmdname in chosencateg["commands"]:
          command = chosencateg["commands"][cmdname]
          cmdusage = ""
          for param in command[0]:
            cmdusage += " " + ("<" if param[0] else "[") + param[1] + (">" if param[0] else "]")
          fullcmdusage = "mom " + cmdname + cmdusage
          embed.description += f'\n\n❯ [`{cmdname}`](https://duckduckgo.com "{fullcmdusage}"){"||`" + cmdusage + "`||" if len(command[0]) > 0 else ""} {command[1]}'
          embed.colour = 0x495619
      else:
        embed.description = "<:download1:739540738223898635> Uh, I could not find that category. Use `mom help` to see a list of categories."
        embed.colour = 0x561927
    embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/802209192990605313/48a8a0c99ee7443a32a3b4b07b9693d4.png?size=256")
    await ctx.send(embed=embed)




@bot.command()
async def pay(ctx, user: discord.Member=None, amount=None):
    if user is None:
      await ctx.send("You must provide a member.")
      return
    if user.bot:
      await ctx.send("You cannot pay a bot!")
      return
    if user.id == ctx.author.id:
      await ctx.send("You cannot pay yourself!")
      return
    if amount is None:
      await ctx.send("You must provide an amount of coins to pay with.")
      return
    if not amount.isnumeric():
      await ctx.send("You must provide an amount of coins to pay with.")
      return
    amount = int(amount)
    if amount > 150000:
      await ctx.send("You cannot pay more than 150 thousand coins at a time!")
      return
    if amount > GetUserCoins(ctx.author.id):
      await ctx.send(f"You don't have that much coins! You only have `{GetUserCoins(ctx.author.id):,d}` coins.")
      return
    maxpayamount = int(GetUserCoins(ctx.author.id) * .75)
    if amount > maxpayamount:
      cmsg = await ctx.send(f"You can't pay more than **75%** of your balance.\n<a:nom_party:720961569730592819> For you that's `{maxpayamount:,d} coins`.\nType `pay` if you want to pay {sanitize(user.name)} `{maxpayamount:,d} coins` instead.")
      def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
      try:
        m = await bot.wait_for("message", timeout=25, check=check)
      except asyncio.TimeoutError:
        await cmsg.delete()
        return
      else:
        await m.delete()
        await cmsg.delete()
        if m.content.lower() == "pay":
          amount = maxpayamount
        else:
          return
    if amount < 1:
      await ctx.send("You cannot pay less than 1 coin.")
      return
    if amount > 5000:
      confmsg = await ctx.send(f"<:big_brain:739540641406779403> **Think now...**\nYou've worked hard for these coins, do you really want to give them away?\nType `ok` to pay {sanitize(user.name)} your `{amount:,d} coins`.")
      def check2(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
      try:
        m = await bot.wait_for("message", timeout=20, check=check2)
      except asyncio.TimeoutError:
        await confmsg.delete()
        await ctx.send("Timed out, you did not confirm!")
        return
      else:
        await confmsg.delete()
        if m.content.lower() == "ok":
          pass
        else:
          await ctx.send("You did not confirm the payment.")
          return
    TakeUserCoins(ctx.author.id, amount)
    AddUserCoins(user.id, amount)
    await AddExperience(ctx, ctx.author.id, 300)
    embed = discord.Embed()
    embed.description = f"{ctx.author.mention} gave [`{amount:,d}`](https://duckduckgo.com \"Coins given\") coins to {user.mention}.\n\n{user.mention} now has `{GetUserCoins(user.id):,d}` coins!"
    embed.colour = 0x45725b
    embed.set_thumbnail(url="https://icons.iconarchive.com/icons/aha-soft/business-toolbar/48/payment-icon.png")
    await ctx.send(ctx.author.mention, embed=embed)




@bot.command()
@casino_only()
async def rob(ctx, user: discord.Member=None):
    if time.time() < ((GetUserAttr(ctx.author.id, "last_rob") or 0) + (3 * 60)):
      await ctx.send("You already robbed someone recently! You are not ready for another robbery yet. Can't you just wait 3 minutes?")
      return
    if user is None:
      await ctx.send("You must provide someone to rob!")
      return
    if user.id == ctx.author.id:
      await ctx.send("You cannot rob yourself!")
      return
    if user.bot:
      await ctx.send("You cannot rob a bot!")
      return
    if not IsGambler(user.id):
      await ctx.send("That person does not have access to the casino and you can therefore not rob them.")
      return
    if GetUserCoins(user.id) < 800:
      await ctx.send("That person does not have enough money to be robbed! They must have at least 800 coins to be robbable.")
      return
    alts = []
    def grrw():
      attempt = random.randrange(0, len(robways))
      return grrw() if attempt in alts else attempt
    for _ in range(3):
      alts.append(grrw())
    embed = discord.Embed()
    embed.title = "This is a robbery"
    embed.description = f"How will you rob {user.mention}?*"
    i = 0
    for idx in alts:
      i += 1
      embed.description += f"\n`{i}. " + robways[idx][0] + "`"
    embed.colour = discord.Colour.blurple()
    embed.set_footer(text="* Choosing a more clever way gives a better chance of robbing them. However more risky robberies gives you more money if you succeed.")
    await ctx.send(embed=embed)
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=40, check=check)
    except asyncio.TimeoutError:
      await ctx.send("You timed out, better luck next time.")
    else:
      m = m.content
      if not m.isnumeric():
        await ctx.send("You should've entered a number, 1-3... you didn't.")
        return
      choice = int(m) - 1
      if choice > 2 or choice < 0:
        await ctx.send(f"That's not a choice, you should've entered a number that is **1, 2, or 3**, not {choice + 1}.")
        return
      robway = robways[alts[choice]]
      successchance = robway[2]
      robsuccess = random.randrange(1, 100) < successchance
      if robsuccess:
        await AddExperience(ctx, ctx.author.id, 50)
        earncoins = random.randrange(1000 - (successchance * 10), 1800 - (successchance * 10))
        TakeUserCoins(user.id, earncoins)
        AddUserCoins(ctx.author.id, earncoins)
        await ctx.send(embed=discord.Embed(
          title=random.choice(["Robbery success", "Nobody noticed", "Mission complete", "True robbery", "Sneaky robbery", "Good job"]),
          description=f"{ctx.author.mention} robbed {user.mention} for **{earncoins:,d} coins**.",
          colour=discord.Colour.green()
        ))
      else:
        await AddExperience(ctx, ctx.author.id, 15)
        losecoins = min(random.randrange(200, 600), GetUserCoins(ctx.author.id))
        TakeUserCoins(ctx.author.id, losecoins)
        AddUserCoins(user.id, losecoins)
        await ctx.send(embed=discord.Embed(
          title=random.choice(["You were CAUGHT!", "Robbery unsuccessful", "Oh no!", "Bad robbery"]),
          description=f"{ctx.author.mention} was caught whilst trying to rob {user.mention} and lost **{losecoins:,d} coins**. Those coins were given to {user.mention}.\n`{robway[1]}`",
          colour=discord.Colour.red()
        ))
      SetUserAttr(ctx.author.id, "last_rob", time.time())

@bot.command()
@level_restrict(2)
async def hangman(ctx):
    if GetUserCoins(ctx.author.id) < 500:
      await ctx.send("You don't have enough coins (500) to do this.")
      return
    selectedword = random.choice(ohangman.words)
    usedcharsgood = [] # used characters, only right ones
    usedchars = [] # used characters, only wrong ones
    async def sendmessage():
      attemptsleft = 10 - len(usedchars)
      if attemptsleft <= 0:
        TakeUserCoins(ctx.author.id, 400)
        await ctx.send(embed=discord.Embed(
          title="<a:goodbye_bush:739540942750613574> Man hanged",
          description=f"You ran out of tries.\nThe word: {selectedword.upper()}\n`-400 coins`",
          colour=discord.Colour.red()
        ))
        return None
      description = f"{ohangman.manimations[attemptsleft - 1]} • {attemptsleft} attempt(s) left.\n\n`"
      for c in selectedword:
        if c in usedcharsgood:
          description += c.upper() + " "
        else:
          description += "_ "
      description += f"` ({len(selectedword)})\n\n**USED:** `" + (", ".join(usedchars) or "none") + "`"
      description += "\nType a letter to guess it or `quit` to quit the game!"
      embed = discord.Embed()
      embed.set_author(name=sanitize(ctx.author.name) + " is playing a game of...")
      embed.title = "Hangman"
      embed.description = description
      embed.colour = discord.Colour.orange()
      return await ctx.send(ctx.author.mention, embed=embed)
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    while True:
      msg = await sendmessage()
      #ran out of attempts
      if msg is None:
        break
      try:
        char = await bot.wait_for("message", timeout=2 * 60, check=check)
      except asyncio.TimeoutError:
        await msg.delete()
        TakeUserCoins(ctx.author.id, 130)
        await ctx.send(embed=discord.Embed(
          title="Oh no!",
          description="You ran out of time to answer. Game over.\nPenalty: `-130 coins`",
          colour=discord.Colour.red()
        ))
        break
      else:
        await msg.delete()
        await char.delete()
        char = char.content.lower()
        if char == "quit":
          penalty = len(usedchars) * 20
          TakeUserCoins(ctx.author.id, penalty)
          await ctx.send(f"<:shibaplease:720961487103066224> **You quit the game!**\nQuit penalty: `-{penalty} coins`")
          return
        if len(char) != 1:
          await ctx.send(embed=discord.Embed(
            title="<:kermit_wot:731598041760399361> Bad guess",
            description="You must type a single letter to guess.",
            colour=discord.Colour.red()
          ))
          continue
        if char not in "abcdefghijklmnopqrstuvwxyz":
          await ctx.send(embed=discord.Embed(
            title="<:kermit_wot:731598041760399361> Bad guess",
            description="Your letter must be alphabetical (a-z).",
            colour=discord.Colour.red()
          ))
          continue
        if char in usedchars or char in usedcharsgood:
          await ctx.send(embed=discord.Embed(
            title="Letter in use",
            description="<a:goodbye_bush:739540942750613574> You have already used this letter.",
            colour=discord.Colour.red()
          ))
          continue
        #successful letter, may be right or wrong
        if char in selectedword:
          #good
          usedcharsgood.append(char)
          await AddExperience(ctx, ctx.author.id, 40)
          #res = await ctx.send(embed=discord.Embed(
          #  title="<:shibacheer:720961100375523369> Good letter",
          #  colour=discord.Colour.green()
          #))
        else:
          #bad
          usedchars.append(char)
          #res = await ctx.send(embed=discord.Embed(
          #  title="<:kermit_wot:731598041760399361> Bad letter",
          #  colour=discord.Colour.red()
          #))
        #await asyncio.sleep(1)
        #await res.delete()
        missingchars = False
        for i in selectedword:
          if i not in usedcharsgood:
            missingchars = True
        if not missingchars:
          AddUserCoins(ctx.author.id, 60)
          await AddExperience(ctx, ctx.author.id, 200)
          await ctx.send(embed=discord.Embed(
            title="<:wow:762241502898290698> " + selectedword.upper(),
            description="Good game!\n`+60 coins`",
            colour=discord.Colour.green()
          ))
          break



@bot.command()
@debugging_only()
@casino_only()
@level_restrict(5)
async def flip(ctx, choice=None, amount=None):
    if choice is None:
      await ctx.send("You have to actually type heads/tails to flip.")
      return
    sides = ["heads", "tails"]
    if choice.lower() not in sides:
      await ctx.send("Invalid coin side, you have to give either heads/tails.")
      return
    if amount is None:
      await ctx.send("No coin amount to bet is provided.")
      return
    if not amount.isnumeric():
      await ctx.send("You must provide the coin amount as a number.")
      return
    amount = int(amount)
    todayint = int(time.time() / 24 / 60 / 60)
    path = "flipwinnings." + str(todayint)
    if ((usercol.find_one({"_id": ctx.author.id}).get("flipwinnings") or {}).get(str(todayint)) or 0) >= 10000:
      await ctx.send("<:jimmy_gurr:730064025127223336> You've won too much money by doing this today. Come back another day to flip a coin.")
      return
    if amount > 5000:
      await ctx.send("You cannot bet for more than 5,000 coins.")
      return
    if amount < 30:
      await ctx.send("You must bet at least 30 coins.")
      return
    if amount > GetUserCoins(ctx.author.id):
      await ctx.send("You don't have that much money!")
      return
    if random.randrange(0, 91) == 90 and amount >= 500:
      await AddExperience(ctx, ctx.author.id, 5000)
      AddUserCoins(ctx.author.id, 10000)
      await ctx.send(embed=discord.Embed(
        title="<:SanjiPepeLaugh:739592274253578260><:SanjiPepeLaugh:739592274253578260> INSANE LUCK!! <:SanjiPepeLaugh:739592274253578260><:SanjiPepeLaugh:739592274253578260>",
        description="Wowowowow!\n**The coin landed on its vertical side!**\n`+10,000` coins!",
        colour=discord.Colour.orange()
      ))
      return
    choice = sides.index(choice.lower())
    coinside = random.randrange(0, 2)
    won = coinside == choice
    embed = discord.Embed()
    embed.title = sides[coinside].upper()
    embed.description = f"{ctx.author.mention} bet `{amount:,d}` coins on `{sides[choice]}` and **" + ("WON" if won else "LOST") + "**!\n`" + (("+" + str(amount * 2)) if won else ("-" + str(amount))) + "coins `"
    embed.colour = discord.Colour.green() if won else discord.Colour.red()
    await ctx.send(embed=embed)
    getcoins = amount * 2 if won else -amount
    await AddExperience(ctx, ctx.author.id, 40 if won else 8)
    AddUserCoins(ctx.author.id, getcoins)
    usercol.update_one({"_id": ctx.author.id}, {
      "$inc": {
        path: getcoins
      }
    }, upsert=True)



@bot.command()
@admin_only()
async def resetstudytokens(ctx):
    await ctx.send("Confirm by typing `herebyiconfirm`.")
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=10, check=check)
    except asyncio.TimeoutError:
      await ctx.send("Timed out.")
    else:
      if m.content == "herebyiconfirm":
        usercol.update_many({"studytokens": {"$exists": True}}, {"$unset": {"studytokens": ""}})
        await ctx.send("All study tokens have been reset.")
      else:
        await ctx.send("You did not type the required message. Nothing happened.")




@bot.command(aliases=["shop"])
async def roleshop(ctx):
    embed = discord.Embed()
    embed.title = "<:blobnom:720961400767381557> Momentum Role Shop"
    embed.description = "In the role shop you can use your well earned coins to buy roles for **channel access and other exclusive abilities**.\nType `mom buyrole [role]` to buy a role.\n**NOTE:** This is the __role__ shop. If you want to buy cards, use `mom packshop` instead.\n"
    for itemname in shopitems:
      item = shopitems[itemname]
      embed.description += f"\n☞ [`{itemname}`](https://duckduckgo.com \"Role name\") <:famcoin2:845382244554113064> `{item[0]:,d}`" + (f" • **Lasts {GetTimeString(item[3])}**" if len(item) >= 4 else "") + (f" (**[OWNED](https://duckduckgo.com \"You own this role, and you cannot buy it\")**)" if discord.utils.get(ctx.author.roles, id=item[2]) else "") + f"\n{item[1]}\n"
    embed.colour = 0x843946
    embed.set_thumbnail(url="https://icons.iconarchive.com/icons/kyo-tux/basket/128/basket-full-icon.png")
    embed.set_footer(text="Use \"mom roles\" to see what temporary roles you own and when they expire.")
    await ctx.send(embed=embed)


@bot.command(aliases=["buy"])
@level_restrict(3)
async def buyrole(ctx, itemname=None):
    if itemname is None:
      await ctx.send("<a:download1:745404052598423635> You have to actually include a role to buy it.")
      return
    itemname = itemname.lower()
    if not itemname in shopitems:
      await ctx.send("<a:download1:745404052598423635> That role does not exist in the role shop, please view the shop to see what we have.")
      return
    item = shopitems[itemname]
    itemrole = discord.utils.get(ctx.guild.roles, id=item[2])
    if itemrole in ctx.author.roles:
      await ctx.send("<a:download1:745404052598423635> You already have this! You cannot buy it.")
      return
    if GetUserCoins(ctx.author.id) < item[0]:
      await ctx.send("<a:download1:745404052598423635> You don't have enough coins to buy this!")
      return
    await AddExperience(ctx, ctx.author.id, 300)
    TakeUserCoins(ctx.author.id, item[0])
    await ctx.author.add_roles(itemrole)
    if len(item) > 3:
      temprolescol.insert_one({
        "expires": time.time() + item[3],
        "role": item[2],
        "user": ctx.author.id
      })
    brole = discord.utils.get(bot.guilds[0].roles, id=item[2])
    await ctx.send(ctx.author.mention, embed=discord.Embed(
      title=f"<:famcoin2:845382244554113064> Purchased {itemname}",
      description=f"You purchased the role {brole.mention} for `{item[0]:,d}` coins.\n> {item[1]}" + (f"\nYou will lose this role in `{GetTimeString(item[3])}`" if len(item) >= 4 else ""),
      colour=0x378c28
    ))



#Here are the new card commands, woo

@bot.command(aliases=["cardshop", "tradecardshop", "packs", "cardpacks"])
async def packshop(ctx):
    embed = discord.Embed()
    embed.title = "<:beaver_2:841722221671743488> Momentum Card Pack Shop"
    embed.description = "Buy some trading card packs here! Each pack contains 1 card.\nType `mom buypack [card pack]` to buy a card pack.\nMomentum Trade Cards are cards that you can buy, sell and trade with! Different card packs contain different cards, collect them all!\n"

    owncards = GetUserAttr(ctx.author.id, "card_inventory") or []

    for packname in tradecards.packs:
      pack = tradecards.packs[packname]
      cardsownedc = []
      for cardid in owncards:
        if cardid in pack["cards"] and not cardid in cardsownedc:
          cardsownedc.append(cardid)
      embed.description += f'\n☞ [`{packname}`](https://duckduckgo.com "Pack name") <:famcoin2:845382244554113064> `{pack["cost"]:,d}` ({len(pack["cards"])} possible cards)' + (f' - **{round((len(cardsownedc) / len(pack["cards"])) * 100)} % collected**' if len(cardsownedc) > 0 else "") + f'\n{pack["description"]}\n'
    embed.colour = 0x136c8c
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/783066135662428180/851746324961558538/unknown.png")
    await ctx.send(embed=embed)


@bot.command(aliases=["buycard", "buycardpack", "buytradecard"])
@level_restrict(5)
async def buypack(ctx, packname=None):
    if packname is None:
      await ctx.send("<:kermit_wot:731598041760399361> You have to include a pack's name to buy it.")
      return
    packname = packname.lower()
    if not packname in tradecards.packs:
      await ctx.send("<:kermit_wot:731598041760399361> That pack does not exist in the shop.")
      return
    pack = tradecards.packs[packname]
    if GetUserCoins(ctx.author.id) < pack["cost"]:
      await ctx.send("<:kermit_wot:731598041760399361> You don't have enough coins to buy this!")
      return
    await AddExperience(ctx, ctx.author.id, 150)
    possiblecards = pack["cards"]
    random.shuffle(possiblecards)
    chosencard = False
    while not chosencard:
      if len(possiblecards) == 0:
        await ctx.send("This pack appears to be empty...")
        chosencard = True
      for card in possiblecards:
        cardobj = tradecards.tradecards[card]
        chance = random.randint(1, 100)
        if chance <= tradecards.rarity_chances[cardobj["rarity"]]:
          #got this card
          TakeUserCoins(ctx.author.id, pack["cost"])
          await AddExperience(ctx, ctx.author.id, 1000)
          omsg = await ctx.send(f'Bought pack for `{pack["cost"]:,d}` coins.\n<a:doge_dance:728195752123433030> **Opening the pack `{packname}` ...** <a:doge_dance:728195752123433030>')
          file = LoadTradecardImage(card)
          await omsg.delete()
          chosencard = True
          duplicate = usercol.count_documents({"_id": ctx.author.id, "card_inventory": {"$in": [card]}}) > 0
          usercol.update_one({"_id": ctx.author.id}, {
            "$push": {"card_inventory": card}
          }, upsert=True)
          dupecount = GetUserAttr(ctx.author.id, "card_inventory").count(card)
          embed = discord.Embed()
          embed.description = f'<:shibacheer:720961100375523369> The pack contained:\n{tradecards.rarity_emojis[cardobj["rarity"]]} [`{tradecards.rarities[cardobj["rarity"]]}` **{cardobj["name"]}**](https://duckduckgo.com "You received this card")\n\n*{sanitize(cardobj["quote"])}*' + (f"\n\nDuplicate card! **{dupecount}x**" if duplicate else "")
          embed.set_image(url="attachment://tradecard.png")
          embed.colour = tradecards.rarity_colours[cardobj["rarity"]]
          await ctx.send(ctx.author.mention, file=file, embed=embed)
          chosencard = True
          break

@bot.command(aliases=["tradecards", "mytradecards", "cardlist", "cards", "cardinventory", "cardinv", "inventory", "inv"])
async def mycards(ctx):
    cards = GetUserAttr(ctx.author.id, "card_inventory") or []
    fixed = {}
    for card in cards:
      if card in fixed:
        continue
      fixed[card] = cards.count(card)
    embed = discord.Embed()
    embed.title = "Study Fam Card Collection"
    embed.description = f'This is your card collection.\n`{len(fixed)}/{len(tradecards.tradecards)}` unique cards (`{len(cards)}` in total).\nUse `mom cardinfo <card>` to see information about a card.\n'
    for card in fixed:
      count = fixed[card]
      card = tradecards.tradecards[card]
      embed.description += f'\n\n[`{card["name"]}`](https://duckduckgo.com "Card name") **{count}x** {tradecards.rarity_emojis[card["rarity"]]}'
    if len(fixed) == 0:
      embed.description += "\nYou own no cards yet."
    embed.set_thumbnail(url="https://icons.iconarchive.com/icons/be-os/be-box/32/Be-Card-Stack-icon.png")
    embed.colour = 0xc6374f
    try:
      await ctx.send(embed=embed)
    except:
      embed.description = "Sorry! You have too many cards to display them <:king_cat:730063415959224320>. How did we get here?\nYou should go merge some of them."
      await ctx.send(embed=embed)

@bot.command(aliases=["card", "cardstats", "aboutcard"])
async def cardinfo(ctx, *, cardname=None):
    if cardname is None:
      await ctx.send("You need to provide the name of a card you want information about.")
      return
    card = None
    cardid = None
    i = 0
    for tcard in tradecards.tradecards:
      if easyfy(tcard["name"]) == easyfy(cardname):
        card = tcard
        cardid = i
        break
      i += 1
    if card is None:
      await ctx.send("There is not a card with such name.")
      return
    if "author" in card:
      author = bot.guilds[0].get_member(card["author"]) or None
    else:
      author = None
    owncount = (GetUserAttr(ctx.author.id, "card_inventory") or []).count(cardid)
    totalowners = usercol.count_documents({
      "card_inventory": {"$in": [cardid]}
    })
#    ownerspercent = (totalowners / len([m for m in bot.guilds[0].members if not m.bot])) * 100
#    if ownerspercent == 0:
#      ownerspercent = int(ownerspercent)
#    elif ownerspercent < 1:
#      ownerspercent = round(ownerspercent, 2)
#    belongingpacks = []
#    for packname in tradecards["packs"]:
#      pack = tradecards.packs[packname]
#      if i in pack["cards"]:
#        belongingpacks.append(packname)

    embed = discord.Embed()
    embed.title = card["name"]
    embed.description = (f'*{sanitize(card["quote"])}*\n\nRarity: {tradecards.rarity_emojis[card["rarity"]]} `{tradecards.rarities[card["rarity"]]}`\nMade by: {author.mention if author else "Unknown"}\nYou own: [`{owncount}x`](https://duckduckgo.com \"You have this many of this card\")\n' if owncount > 0 else "") + f'{totalowners} people have this card'
    if owncount > 0:
      embed.colour = tradecards.rarity_colours[card["rarity"]]
      embed.set_image(url="attachment://tradecard.png")
      await ctx.send(file=LoadTradecardImage(cardid), embed=embed)
    else:
      embed.description += "\n\n**This trade card is yet unknown to you.**"
      embed.colour = 0x4c4c4c
      embed.set_image(url="https://cdn.discordapp.com/attachments/825723008957415444/859459704324096020/unknown_card_improved_darker.png")
      await ctx.send(embed=embed)




def easyfy(string):
    return "".join(c for c in string if c.isalpha() or c.isdigit()).lower()



def StringToTime(timestr):
    units = {
      "w": 7 * 24 * 60 * 60,
      "d": 24 * 60 * 60,
      "h": 60 * 60,
      "m": 60,
      "s": 1
    }
    givenunits = timestr.split(" ")
    totaltime = 0
    for u in givenunits:
      cu = u[-1:]
      ct = u[:-1]
      if not ct.isnumeric():
        #invalid format
        raise TimeString_InvalidFormat()
      if cu not in units:
        if not cu.isnumeric():
          #invalid unit
          raise TimeString_InvalidUnit()
        else:
          #missing unit at end
          raise TimeString_MissingUnit()
      totaltime += int(int(ct) * units[cu])
    return totaltime


@bot.command(aliases=["addgoal", "makegoal", "creategoal", "newgoal"])
async def setgoal(ctx, *, ftime=None):
    if (GetUserAttr(ctx.author.id, "dailygoal") or [0, 0, 0])[2] == math.floor(time.time() / 24 / 60 / 60):
      await ctx.send("<a:download1:745404052598423635> You already have a goal for today. Type `mom mygoal` for more information.")
      return
    if ftime is None:
      await ctx.send("<a:download1:745404052598423635> You must provide a time amount to set todays goal to.\nExample: `2h 30m`")
      return
    totaltime = StringToTime(ftime)
    if totaltime < 5 * 60:
      await ctx.send("<a:download1:745404052598423635> Your goal must be at least 5 minutes.")
      return
    if totaltime > 12 * 60 * 60:
      await ctx.send("<a:download1:745404052598423635> What are you doing??\nDon't put your goal that high, max 12 hours.")
      return
    if totaltime >= 4 * 60 * 60:
      await NewPrestige(ctx.author.id, "planner")
    SetUserAttr(ctx.author.id, "dailygoal", [totaltime, totaltime, math.floor(time.time() / 24 / 60 / 60)])
    await AddExperience(ctx, ctx.author.id, 200)
    await ctx.send(ctx.author.mention, embed=discord.Embed(
      description=f"<:wow:762241502898290698> Your goal of `{GetTimeString(totaltime)}` has been made, start studying and try[*](https://discord.com/channels/712808127539707927/713177565849845849/822971544098963456 \"Click for motivation\") reach it!",
      colour=discord.Colour.green()
      ))



@bot.command(aliases=["goal"])
async def mygoal(ctx):
    if not (GetUserAttr(ctx.author.id, "dailygoal") or [0, 0, 0])[2] == math.floor(time.time() / 24 / 60 / 60):
      await ctx.send("You have not set a study goal for today (or you've already completed it). Set a goal with `mom setgoal`.")
      return
    goalarr = GetUserAttr(ctx.author.id, "dailygoal")
    tleft = goalarr[1]
    ttot = goalarr[0]
    await ctx.send(f"<a:doge_dance:728195752123433030> **Study goal of today**\n`{GetTimeString(ttot - tleft)} out of {GetTimeString(ttot)}`\n(`{int((ttot - tleft) / ttot * 100)}%` complete, `{GetTimeString(tleft)}` left)")



@bot.command()
@admin_only()
async def globalgift(ctx, key=None, value=None):
    if None in [key, value]:
      await ctx.send("Both key and value must be provided.")
      return
    if not value.isnumeric():
      await ctx.send("Value must be a number.")
      return
    usercol.update_many({}, {"$inc": {key: int(value)}})
    await ctx.send("Gifted everyone.")


@bot.command()
@admin_only()
async def dbgift(ctx, member: discord.Member=None, key=None, value=None):
    if member is None:
      await ctx.send("You must provide a member to gift.")
      return
    if None in [key, value]:
      await ctx.send("Both key and value must be provided.")
      return
    if not value.isnumeric():
      await ctx.send("Value must be a number.")
      return
    usercol.update_many({"_id": member.id}, {"$inc": {key: int(value)}}, upsert=True)
    await ctx.send(f"Gifted {sanitize(member.name)}.")


@bot.command()
@admin_only()
async def dbungift(ctx, member: discord.Member=None, key=None, value=None):
    if member is None:
      await ctx.send("You must provide a member to ungift.")
      return
    if None in [key, value]:
      await ctx.send("Both key and value must be provided.")
      return
    if not value.isnumeric():
      await ctx.send("Value must be a number.")
      return
    usercol.update_many({"_id": member.id}, {"$inc": {key: -int(value)}}, upsert=True)
    await ctx.send(f"Ungifted {sanitize(member.name)}.")


@bot.command()
@admin_only()
async def viewstats(ctx, stat_id=""):
    data = (statscol.find_one({"_id": stat_id}) or {}).get("data")
    todayint = int(time.time() / 24 / 60 / 60)
    if data is None:
      await ctx.send("No data for that statistic.")
      return
    embed = discord.Embed()
    embed.title = "Statistic"
    embed.description = f"ID: `{stat_id}`\n\n"
    sv = ["", "", "", "", "", ""]
    lastdays = [0, 0, 0, 0, 0, 0, 0]
    for day in data:
      if int(day) > (todayint - len(lastdays)):
        lastdays[todayint - int(day)] = data[day]
    lastdays.reverse()
    stdict = {
      "0": 30,#000,
      "1": 25,#000,
      "2": 20,#000,
      "3": 15,#000,
      "4": 10,#000,
      "5": 5#000
    }
    for row in lastdays:
      #first day goes first, today comes last
      for i in range(len(sv)):
        sv[i] += " ■" if (row >= stdict[str(i)]) else "  "
    for i in range(len(sv)):
      sv[i] += f"   {stdict[str(i)]}"
    embed.description += "```\n" + ("\n".join(sv)) + "\n```"
    embed.colour = discord.Colour.orange()
    await ctx.send(embed=embed)


@bot.command()
async def daily(ctx):
    dailyclaim = GetUserAttr(ctx.author.id, "dailyclaim") or 0
    todayint = int(time.time() / 60 / 60 / 24)
    if dailyclaim == todayint:
      await ctx.send(f"<a:download1:745404052598423635> You have already claimed your daily reward!\nYou can claim it again in **{GetTimeString(((todayint + 1) * 60 * 60 * 24) - time.time())}**.")
      return
    SetUserAttr(ctx.author.id, "dailyclaim", todayint)
    earncoins = 150
    AddUserCoins(ctx.author.id, earncoins)
    await ctx.send(f"<a:CS_Wiggle:856616923915878411> **Claimed daily reward!**\n`+{earncoins} coins`\nYou can claim it again in **{GetTimeString(((todayint + 1) * 60 * 60 * 24) - time.time())}**.")

@bot.command()
@admin_only()
async def addcoins(ctx, member: discord.Member=None, coins=None):
    if member is None:
      await ctx.send("You must provide a server member to add the coins to.")
      return
    if coins is None:
      await ctx.send("You must provide a number of coins to give the user.")
      return
    if not coins.isnumeric():
      await ctx.send("Coins must be a number.")
      return
    coins = int(coins)
    if coins > 15000:
      await ctx.send("Too many coins!")
      return
    AddUserCoins(member.id, coins)
    await ctx.send(f'Added {coins} coins to {member.name}\'s balance.')

@bot.command(aliases=["removecoins"])
@admin_only()
async def takecoins(ctx, member: discord.Member=None, coins=None):
    if member is None:
      await ctx.send("You must provide a server member to remove the coins from.")
      return
    if coins is None:
      await ctx.send("You must provide a number of coins to take from the user.")
      return
    if not coins.isnumeric():
      await ctx.send("Coins must be a number.")
      return
    coins = int(coins)
    if coins > 15000:
      await ctx.send("Too many coins to take!")
      return
    TakeUserCoins(member.id, coins)
    await ctx.send(f'Removed {coins} coins from {member.name}\'s balance.')

@bot.command()
@admin_only()
async def setcoins(ctx, member: discord.Member=None, coins=None):
    if member is None:
      await ctx.send("You must provide a server member to set the coins for.")
      return
    if coins is None:
      await ctx.send("You must provide a number of coins to set the user's balance to.")
      return
    if not coins.isnumeric():
      await ctx.send("Coins must be a number.")
      return
    coins = int(coins)
    if coins > 1000000:
      await ctx.send("Too many coins!")
      return
    AddUserCoins(member.id, coins - GetUserCoins(member.id))
    await ctx.send(f'Set {member.name}\'s balance to {coins} coins.')

@bot.command()
@admin_only()
async def setlevel(ctx, member: discord.Member=None, level=None):
    if member is None:
      await ctx.send("You must provide a server member to set the level on.")
      return
    if level is None:
      await ctx.send("You must provide a level to make the user.")
      return
    if not level.isnumeric():
      await ctx.send("Level must be a number.")
      return
    level = int(level)
    if level > 200:
      await ctx.send("Too high level!")
      return
    requiredxp = 0
    i = 0
    while True:
      if i >= level:
        break
      reqxplevel = math.floor((i + 5) ** 4)
      requiredxp += reqxplevel
      i += 1
    usercol.update_one({"_id": member.id}, {"$set": {"experience": requiredxp}}, upsert=True)
    await ctx.send(f"Set level {level} for **{sanitize(member.name)}**. ({requiredxp}xp)")


@bot.command()
@admin_only()
async def showdoc(ctx, member: discord.Member=None):
    if member is None:
      await ctx.send("No member provided.")
      return
    doc = usercol.find_one({"_id": member.id}) or {}
    embed = discord.Embed()
    desc = "```json\n{\n"
    for key in doc:
      desc += f"\n\"{key}\": {doc[key]},"
    desc += "\n\n}\n```"
    embed.description = desc
    embed.colour = discord.Colour.orange()
    await ctx.send(embed=embed)


@bot.command()
async def toggletokens(ctx):
    mode = not NoTokens(ctx.author.id) # whether study tokens are enabled right now or not
    if not mode:
      RemUserAttr(ctx.author.id, "no_tokens")
      await ctx.send("<:shibahey:720967927435755590> **Study tokens have been enabled.**")
    else:
      if GetUserTokens(ctx.author.id) > 80000:
        await ctx.send("<:5207_blobsadpats:806270586426621992> You have too many study tokens to disable them! Please wait for them to be reset (at the end/beginning of months) or ask staff to remove them.")
        return
      cmsg = await ctx.send(f"<:think:767503923543932948> **Do you really want to disable study tokens?**\nIf you disable study tokens, you will lose them and will not get them back if you enable them again!\nYou have `{GetUserTokens(ctx.author.id)}` study tokens.\nType `disable` to disable study tokens as well as lose them.")
      def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
      try:
        m = await bot.wait_for("message", timeout=40, check=check)
      except asyncio.TimeoutError:
        await cmsg.delete()
        await ctx.send("Study tokens were not disabled, you did not confirm in time.")
      else:
        await m.delete()
        await cmsg.delete()
        if m.content.lower() == "disable":
          RemUserAttr(ctx.author.id, "studytokens")
          SetUserAttr(ctx.author.id, "no_tokens", True)
          await ctx.send("<:comfy_blob:730063563892195408> **Disabled study tokens!**")
        else:
          await ctx.send("Alright, study tokens were not disabled.")




@bot.command(aliases=["trivia", "playtrivia"])
@level_restrict(5)
async def summontrivia(ctx, questions=None):
    if questions is not None:
      if not questions.isnumeric():
        await ctx.send("Non-numeric question amount given!")
        return
      questions = int(questions)
    else:
      questions = 5
    await ctx.message.delete()
    await SummonTrivia(channel=ctx.channel.id, questions=questions)


async def NewPrestige(uid, prestige):
    userprestiges = GetUserAttr(uid, "prestigelist") or []
    prestige = prestigelist[prestige]
    if prestige not in userprestiges:
      userprestiges.append(prestige)
      SetUserAttr(uid, "prestigelist", userprestiges)
      user = bot.guilds[0].get_member(uid)
      await AddExperience(user, uid, prestige[2])
      embed = discord.Embed()
      embed.set_author(name="New prestige!")
      embed.title = prestige[0]
      embed.description = f"<a:nom_party:720961569730592819> *{prestige[1]}*\n`+{prestige[2]} experience`"
      embed.colour = discord.Colour.purple()
      try:
        await user.send(embed=embed)
      except:
        pass


@bot.command()
async def prestiges(ctx):
    myprestiges = GetUserAttr(ctx.author.id, "prestigelist") or []
    embed = discord.Embed()
    embed.title = "Your prestiges"
    for prestige in myprestiges:
      embed.add_field(name=prestige[0], value=prestige[1])
    embed.description = "[What are prestiges?](https://discord.com/channels/712808127539707927/713177565849845849/809420332376653864 \"Read about prestiges\")"
    if len(prestigelist) == 0:
      embed.description += "You have no prestiges."
    embed.colour = 0x757a5f
    await ctx.send(embed=embed)


@bot.command(aliases=["addtrivia", "maketrivia", "triviaquestion", "addtriviaquestion"])
@level_restrict(12)
async def makequestion(ctx):
    if ctrcol.count_documents({"author": ctx.author.id}) >= 20:
      await ctx.send("You have reached the max amount of own trivia questions possible, and you cannot submit another trivia question!")
      return
    question = None
    answer = None
    difficulty = None
    genre = None
    cmsg = await ctx.send(embed=discord.Embed(
      description="<:shibahey:720967927435755590> You're adding a question to trivia. Please read [the guidelines](https://discord.com/channels/712808127539707927/713177565849845849/813705379191455795 \"Show the guidelines\") before submitting your trivia question!\nType `confirm` if you have read the guidelines and want to continue making the trivia question.",
      colour=0x1c684d
    ))
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=4 * 60, check=check)
    except asyncio.TimeoutError:
      await cmsg.delete()
      await ctx.send("Timed out.")
    else:
      await m.delete()
      await cmsg.delete()
      m = m.content.lower()
      if m == "confirm":
        eqmsg = await ctx.send(ctx.author.mention, embed=discord.Embed(
          description="<a:doge_dance:728195752123433030> Type the __question__ for your trivia.\n*16-80 characters*",
          colour=discord.Colour.purple()
        ))
        try:
          m = await bot.wait_for("message", timeout=2 * 60, check=check)
        except asyncio.TimeoutError:
          await eqmsg.delete()
          await ctx.send("Timed out while waiting for question.")
        else:
          await m.delete()
          await eqmsg.delete()
          m = m.content
          if len(m) < 16 or len(m) > 80:
            await ctx.send("Question length must be 16-80 characters. Your trivia has not been added.")
            return
          question = m
          eamsg = await ctx.send(ctx.author.mention, embed=discord.Embed(
            description="<a:doge_dance:728195752123433030> Type the __answer__ for your trivia.\n*1-18 characters*",
            colour=discord.Colour.purple()
          ))
          try:
            m = await bot.wait_for("message", timeout=3 * 60, check=check)
          except asyncio.TimeoutError:
            await eamsg.delete()
            await ctx.send("Timed out while waiting for answer.")
          else:
            await m.delete()
            await eamsg.delete()
            m = m.content
            if len(m) < 1 or len(m) > 18:
              await ctx.send("Answer length must be 1-18 characters. Your trivia has not been added.")
              return
            answer = m
            edmsg = await ctx.send(ctx.author.mention, embed=discord.Embed(
              description="<a:doge_dance:728195752123433030> Set the __difficulty__ for your trivia.\n\n**1.** Easy\n**2.** Moderate\n**3.** Hard",
              colour=discord.Colour.purple()
            ))
            try:
              m = await bot.wait_for("message", timeout=60, check=check)
            except asyncio.TimeoutError:
              await eqmsg.delete()
              await ctx.send("Timed out while waiting for difficulty.")
            else:
              await m.delete()
              await edmsg.delete()
              m = m.content
              if not m.isnumeric():
                await ctx.send("You should've typed a number! Your trivia has not been added.")
                return
              m = int(m) - 1
              if m < 0 or m > len(trivia.diffs) - 1:
                await ctx.send("The number must be 1-3! Your trivia has not been added.")
                return
              difficulty = m
              embed = discord.Embed()
              embed.colour = discord.Colour.purple()
              embed.description = "<a:doge_dance:728195752123433030> Set the __genre__ for your trivia.\n"
              i = 1
              for genre in trivia.genres:
                embed.description += f"\n**{i}.** `{genre}`"
                i += 1
              egmsg = await ctx.send(ctx.author.mention, embed=embed)
              try:
                m = await bot.wait_for("message", timeout=2 * 60, check=check)
              except asyncio.TimeoutError:
                await egmsg.delete()
                await ctx.send("Timed out while waiting for genre.")
              else:
                await m.delete()
                await egmsg.delete()
                m = m.content
                if not m.isdigit():
                  await ctx.send("You should've typed a number! Your trivia has not been added.")
                  return
                m = int(m) - 1
                if m < 0 or m > len(trivia.genres) - 1:
                  await ctx.send(f"The number must be 1-{len(trivia.genres)}! Your trivia has not been added.")
                  return
                genre = m
                smsg = await ctx.send(embed=discord.Embed(
                  title="Submit trivia?",
                  description=f"<:shibaplease:720961487103066224> Thank you so much for supporting Momentum by adding trivia questions!\n**Do you want to submit this trivia?**\n*Note that your trivia may be removed if it does not follow the guidelines or the rules. You cannot play your own trivia. You cannot manage/change/remove your trivia once submitted without contacting staff.*\n**Your trivia:**\nQuestion: `{sanitize(question)}`\nAnswer: `{sanitize(answer)}`\nDifficulty: `{trivia.diffs[difficulty]}`\nGenre: `{trivia.genres[genre]}`\n**Type `submit` if you want to submit this trivia.**",
                  colour=discord.Colour.orange()
                ))
                try:
                  m = await bot.wait_for("message", timeout=2 * 60, check=check)
                except asyncio.TimeoutError:
                  await smsg.delete()
                  await ctx.send("You did not submit in time.")
                else:
                  await m.delete()
                  await smsg.delete()
                  m = m.content.lower()
                  if m == "submit":
                    ctrcol.insert_one({
                      "question": question,
                      "answer": answer,
                      "difficulty": difficulty,
                      "genre": genre,
                      "author": ctx.author.id
                    })
                    LoadTriviaQuestions()
                    await AddExperience(ctx, ctx.author.id, 350)
                    await ctx.send("<:shibacheer:720961100375523369> **Trivia submitted!**\nYour trivia has been added and is playable.\nIf you wish to remove the trivia, please contact staff.")
                  else:
                    await ctx.send("You did not confirm, and your trivia was not submitted.")
      else:
        await ctx.send("You did not confirm.")



async def UpdateBountyMessage(refid):
    doc = bntcol.find_one({"_id": refid})
    if doc is None:
      return
    oc = bot.get_channel(channels.Officer)
    msg = await oc.fetch_message(doc.get("message_id"))
    provider = bot.guilds[0].get_member(doc.get("provider"))
    statusicon = "✓" if not doc.get("claimed") else "🞬"
    statusmode = "AVAILABLE" if not doc.get("claimed") else "TAKEN"
    deposit = doc.get("input")
    description = doc.get("description")
    embed = discord.Embed()
    embed.title = "<a:doge_dance:728195752123433030> New Bounty!"
    embed.description = f"Fellow officers, here is a bounty.\nClaim it with `mom claimbounty {refid}`!\n\nCreated by: {provider.mention}\nChallenge: `{description}`\nPrize: <:famcoin2:845382244554113064> `{deposit:,d}`\nClaim status: [{statusicon} **{statusmode}**](https://duckduckgo.com \"Whether this bounty is claimable or not\")" + (" (<@" + str(doc.get("claimed_by")) + ">)" if doc.get("claimed") else "")
    embed.set_thumbnail(url="https://i.imgur.com/SchZkD8.png")
    embed.colour = 0x7a3333
    await msg.edit(content="", embed=embed)





@bot.command(aliases=["startbounty", "bounty"])
async def makebounty(ctx, binput=None, *, description=None):
    if ctx.channel.id != channels.Officer:
      await ctx.send("To create a bounty you must run this command in the officer channel.")
      return
    if bntcol.count_documents({"provider": ctx.author.id}) > 0:
      if bntcol.count_documents({"provider": ctx.author.id, "expires": {"$gt": time.time()}}):
        chclaimed = bntcol.find_one({"provider": ctx.author.id}).get("claimed")
        await ctx.send("You already have a bounty!\n" + ("Your bounty challenge has not been claimed yet! Type `mom cancelbounty` to cancel it before someone claims it." if not chclaimed else "The bounty cannot be canceled because the challenge has already been claimed by someone. You must succeed or fail the bounty challenge or wait until it has expired."))
        return
      else:
        #delete bounty if it has expired
        bntcol.delete_one({"provider": ctx.author.id})
    if binput is None:
      await ctx.send("You did not provide the amount of coins you are willing to give the officer taking upon this bounty if you fail the challenge. Your bounty has not been created.")
      return
    if not binput.isnumeric():
      await ctx.send("The coins your provided are not in numbers. Your bounty has not been created.")
      return
    binput = int(binput)
    if binput < 100:
      await ctx.send("You must offer at least 100 coins to the person who claims the bounty!")
      return
    if binput > GetUserCoins(ctx.author.id):
      await ctx.send(f"You don't have that many coins! You only have `{GetUserCoins(ctx.author.id)}`!")
      return
    if description is None:
      await ctx.send("You did not provide a description for your bounty. You must have a description so that people can know what the bounty is about and what they should do. Your bounty has not been created.")
      return
    if len(description) < 15:
      await ctx.send("Bounty description must be at least 15 characters. Your bounty has not been created.")
      return
    if len(description) > 450:
      await ctx.send("Bounty description cannot be longer than 450 characters. Your bounty has not been created.")
      return
    bntid = random.randrange(10 ** 2, 10 ** 3)
    emsg = await ctx.send("Loading bounty, please wait...")
    TakeUserCoins(ctx.author.id, binput)
    bntcol.insert_one({
      "_id": bntid,
      "provider": ctx.author.id,
      "claimed": False,
      "input": binput,
      "expires": time.time() + (8 * 60 * 60),
      "description": sanitize(description),
      "message_id": emsg.id
    })
    await UpdateBountyMessage(bntid)


@bot.command()
async def cancelbounty(ctx):
    if ctx.channel.id != channels.Officer:
      await ctx.send("To cancel your bounty you must run this command in the officer channel.")
      return
    # no bounty exists
    if bntcol.count_documents({"provider": ctx.author.id}) == 0:
      await ctx.send("You don't have an ongoing bounty!")
      return
    doc = bntcol.find_one({"provider": ctx.author.id})
    # bounty is claimed and it has not expired
    if doc.get("claimed") and doc.get("expires") > time.time():
      await ctx.send("You cannot cancel your bounty challenge because it has already been claimed by someone! You must succeed or fail the bounty challenge or wait until it has expired.")
      return
    bntcol.delete_one({"provider": ctx.author.id})
    await ctx.send(ctx.author.mention + "\nYour bounty has been canceled!\nYou did **not** get your bounty input of `" + str(doc.get("input")) + "` coins back.")



@bot.command(aliases=["takebounty"])
async def claimbounty(ctx, refid=None):
    if bntcol.count_documents({"claimed_by": ctx.author.id, "expires": {"$gt": time.time()}}) > 0:
      await ctx.send("You are already assigned to a bounty! That bounty must be finished before you can claim a new one.")
      return
    if not discord.utils.get(bot.guilds[0].roles, id=738023376584441867) in ctx.author.roles:
      await ctx.send("You must be an officer to claim bounty missions. Go ahead and get it from the shop!")
      return
    if refid is None:
      await ctx.send("You must provide a bounty ID to claim it.")
      return
    if not refid.isnumeric():
      await ctx.send("Bounty ID must be a number.")
      return
    refid = int(refid)
    doc = bntcol.find_one({"_id": refid})
    if doc is None:
      await ctx.send("A bounty with that ID does not exist.")
      return
    if doc.get("claimed"):
      await ctx.send("That bounty is already claimed!")
      return
    if time.time() > doc.get("expires"):
      await ctx.send("That bounty has expired.")
      return
    if doc.get("provider") == ctx.author.id:
      await ctx.send("That is YOUR bounty! You cannot claim your own bounty, someone else has got to do it.")
      return
    bntcol.update_one({"_id": refid}, {"$set": {"claimed": True, "claimed_by": ctx.author.id}})
    await ctx.send(ctx.author.mention + f"\n**Claimed bounty!**\nYou have claimed the bounty with ID `{refid}`.")
    await ctx.send(bot.guilds[0].get_member(doc.get("provider")).mention + f"\n`{sanitize(ctx.author.name)}` has claimed your bounty.")
    await UpdateBountyMessage(refid)


@bot.command()
async def finishbounty(ctx):
    if bntcol.count_documents({"claimed_by": ctx.author.id}) == 0:
      await ctx.send("<:facepalm:739540188136734797> You haven't claimed any bounty!")
      return
    doc = bntcol.find_one({"claimed_by": ctx.author.id})
    if doc.get("expires") < time.time():
      await ctx.send("You have had a claimed bounty, but it expired `" + GetTimeString(time.time() - doc.get("expires")) + "` ago and cannot be finished.\nYou can claim a new bounty.")
      return
    coindeposit = doc.get("input")
    provider = bot.guilds[0].get_member(doc.get("provider"))
    fsmsg = await ctx.send(f"{ctx.author.mention}\n<a:download1:745404052598423635> Did `{sanitize(provider.name)}` complete their challenge?\nType `yes` or `no`.")
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
      await fsmsg.delete()
      await ctx.send("Timed out while waiting for bounty challenge completion result answer. Nothing happened.")
    else:
      await m.delete()
      await fsmsg.delete()
      m = m.content.lower()
      choices = ["yes", "no"]
      if m in choices:
        choice = choices.index(m)
        if choice == 0:
          #give back money to provider
          AddUserCoins(provider.id, coindeposit)
          await AddExperience(ctx.channel, ctx.author.id, 4000)
          await AddExperience(ctx.channel, provider.id, 4000)
        else:
          #give money to bounty claimer
          AddUserCoins(ctx.author.id, coindeposit)
          await AddExperience(ctx.channel, ctx.author.id, 4000)
          await AddExperience(ctx.channel, provider.id, 250)
        bntcol.delete_one({"_id": doc.get("_id")})
        oc = bot.get_channel(channels.Officer)
        url = (await oc.fetch_message(doc.get("message_id"))).jump_url
        resulttext = "✓ ACCOMPLISHED" if choice == 0 else "🞬 FAILED"
        embed = discord.Embed()
        embed.title = "Bounty Challenge Finished!"
        embed.colour = discord.Colour.green()
        embed.description = f"{provider.mention} [{resulttext}]({url} \"Bounty challenge result\") their bounty challenge!\n" + (f"{provider.mention} got their coins back." if choice == 0 else f"{ctx.author.mention} got {provider.mention}'s `{coindeposit:,d}` coins.")
        await ctx.send(provider.mention + ctx.author.mention, embed=embed)
      else:
        await ctx.send("<:facepalm:739540188136734797> That was not a valid option. Nothing happened.")





@bot.command(aliases=["createreminder", "createtimer", "makereminder", "maketimer", "timer", "remindme"])
async def reminder(ctx, *, ftime=None):
    if timcol.count_documents({"owner": ctx.author.id}) >= 5:
      await ctx.send("Max 5 timers at once!")
      return
    await ctx.message.delete()
    tamsg = await ctx.send(ctx.author.mention + "\n<a:doge_dance:728195752123433030> How long should the timer be set to?\nE.g. `1h 30m`")
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=60, check=check)
    except asyncio.TimeoutError:
      await tamsg.delete()
      await ctx.send("Timed out while waiting for time amount.")
    else:
      await m.delete()
      await tamsg.delete()
      m = m.content
      totaltime = StringToTime(m)
      if totaltime > 10 * 60 * 60:
        await ctx.send("Max 10 hours for timer. The timer has not been set.")
        return
      if totaltime < 30:
        await ctx.send("At least 30 seconds for timer. The timer has not been set.")
        return
      tmmsg = await ctx.send(ctx.author.mention + "\n<a:doge_dance:728195752123433030> What should the message be?\nType `none` to ignore message.")
      try:
        m = await bot.wait_for("message", timeout=60, check=check)
      except asyncio.TimeoutError:
        await tmmsg.delete()
        await ctx.send("Timed out while waiting for timer message.")
      else:
        await m.delete()
        await tmmsg.delete()
        m = m.content
        timermessage = sanitize(m)
        if m.lower() == "none":
          timermessage = None
        timcol.insert_one({
          "owner": ctx.author.id,
          "remind_at": time.time() + totaltime,
          "totaltimer": totaltime,
          "message": timermessage
        })
        await ctx.send(f"{ctx.author.mention}\n<a:doge_dance:728195752123433030> **Reminder created!**\nI will remind you in `{GetTimeString(totaltime)}`" + (f" with `{timermessage}`" if timermessage != None else "") + ".")
        asyncio.get_event_loop().create_task(LoadTimers())

@bot.command(aliases=["mytimers", "listreminders", "listtimers", "reminderlist", "timerlist", "reminders", "timers"])
async def myreminders(ctx):
    ownreminders = timcol.find({"owner": ctx.author.id})
    remindercount = timcol.count_documents({"owner": ctx.author.id})
    text = f"<:hourglass:816596944330817536> You have `{remindercount}` reminder(s)."
    i = 0
    for reminder in ownreminders:
      i += 1
      totaltime = reminder.get("totaltimer")
      timeleft = reminder.get("remind_at") - time.time()
      text += f"\n**{i}.**" + (f" `" + reminder.get("message") + "` -" if reminder.get("message") != None else "") + f" `{GetTimeString(totaltime)}` (`{GetTimeString(timeleft)}` remaining)"
    if remindercount > 0:
      text += "\nUse `mom clearreminder <index>` to delete a reminder."
    await ctx.send(text)

@bot.command(aliases=["cleartimer", "deletereminder", "deletetimer", "removereminder", "removetimer"])
async def clearreminder(ctx, index=None):
    if index is None:
      await ctx.send("You must provide the index of a reminder to remove.")
      return
    if not index.isnumeric():
      await ctx.send("Reminder index must be a number.")
      return
    index = int(index)
    remindercount = timcol.count_documents({"owner": ctx.author.id})
    if index > remindercount or index < 1:
      await ctx.send("You don't have a reminder with that index.")
      return
    reminder = timcol.find({"owner": ctx.author.id}).skip(index - 1).limit(1)[0]
    timcol.delete_one({"_id": reminder.get("_id")})
    await ctx.send(f"Reminder at index `{index}` has been deleted. Now you have `{remindercount - 1}` reminder(s) left.")



def LoadTradecardImage(idx):
    obj = tradecards.tradecards[idx]
    frame = Image.open("images/frames/" + ["common", "uncommon", "rare", "legendary", "god"][obj["rarity"]] + ".png").convert("RGBA")
    tradecard = Image.open(tradecards.folderpath + obj["image"]).convert("RGBA")
    framedcard = Image.new("RGBA", frame.size)
    #height for old frames: 25px. For new: 56px
    framedcard.paste(tradecard, (34, 25), tradecard)
    framedcard.paste(frame, (0, 0), frame)

    text = Image.new("RGBA", framedcard.size, (255, 255, 255, 0))
    if "author" in obj:
      author = bot.guilds[0].get_member(obj["author"]) or None
    else:
      author = None
    draw = ImageDraw.Draw(text)
    font = ImageFont.truetype("fonts/OpenSans-Regular.ttf", 25)
    draw.text((75, 1100), (f"Made by {author.name}#{author.discriminator}" if author else "Unknown creator"), (0, 0, 0, 128), font=font)

    creditedtradecard = Image.alpha_composite(framedcard, text)

    if author:
      avatar = Image.open(requests.get(author.avatar_url_as(size=32), stream=True).raw).convert("RGBA")
      creditedtradecard.paste(avatar, (43, 1100))

    temppath = tempfp()
    creditedtradecard.save(temppath)
    file = discord.File(temppath, filename="tradecard.png")
    os.remove(temppath)
    return file



@bot.command()
async def credits(ctx):
    embed = discord.Embed()
    embed.title = "Momentum Credits"
    embed.description = """
    **=== Programming ===**
    • Developer: <@482459199213928459>
    **=== Trade cards ===**
    *Thank you so much for making the awesome cards!*
    • Lead artist: <@307999381213151243>
    • Artist: <@277708587554308096>
    • Artist: <@645256353966981120>
    • Feedback contact: <@195258903368302592>
    **=== Other ===**
    • Logo creator: <@277708587554308096>
    """
    ctna = [
      482459199213928459, #crunchyfrog
      195258903368302592, #archetim
      #307999381213151243, #ricestew
      277708587554308096, #anivya
      645256353966981120, #amelia
    ]
    imgs = []
    frames = 30
    for a in ctna:
      o = Image.open(requests.get((bot.guilds[0].get_member(a)).avatar_url_as(size=128), stream=True).raw)
      #pre-transition
      for tr in range(frames):
        t = Image.new("RGB", (128, 128))
        t.paste(o, (int((128 / frames) * tr) - 128, 0))
        imgs.append(t)
      #still image
      imgs += 30 * [o]
      #post-transition
      for tr in range(frames):
        t = Image.new("RGB", (128, 128))
        t.paste(o, (int((128 / frames) * tr), 0))
        imgs.append(t)
    temppath = tempfp(ext="gif")
    imgs[0].save(fp=temppath, format="GIF", append_images=imgs[1:], save_all=True, duration=50, loop=0)
    file = discord.File(temppath, filename="slideshow.gif")
    os.remove(temppath)
    embed.set_thumbnail(url="attachment://slideshow.gif")
    embed.colour = 0x04775d
    await ctx.send(file=file, embed=embed)



def tempfp(ext="png"):
    return f"images/temp/{random.randint(1, 99)}.{ext}"



@bot.command(aliases=["tradecardmerge", "mergetradecards", "cardmerge"])
@level_restrict(10)
async def mergecards(ctx):
    crmsg = await ctx.send(ctx.author.mention + "\nWhat card rarity do you want to merge?")
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=40, check=check)
    except asyncio.TimeoutError:
      await crmsg.delete()
      await ctx.send("Timed out while waiting for rarity to merge.")
    else:
      await crmsg.delete()
      await m.delete()
      m = m.content.lower()
      mergerarity = None
      if m in ["legendary", "god"]:
        await ctx.send("You cannot merge that rarity.")
        return
      elif m == "rare":
        mergerarity = 2
      elif m == "uncommon":
        mergerarity = 1
      elif m == "common":
        mergerarity = 0
      else:
        await ctx.send("That rarity does not exist. The rarities you can merge are `common`, `uncommon` and `rare`.")
        return
      chosencards = []
      requiredcards = 5
      while True:
        if len(chosencards) == requiredcards:
          newarray = GetUserAttr(ctx.author.id, "card_inventory") or []
          for remcard in chosencards:
            newarray.remove(remcard)
          SetUserAttr(ctx.author.id, "card_inventory", newarray)
          choosefrom = []
          i = 0
          for tcard in tradecards.tradecards:
            if tcard["rarity"] == mergerarity + 1:
              choosefrom.append(i)
            i += 1
          card = random.choice(choosefrom)
          cardobj = tradecards.tradecards[card]
          duplicate = usercol.count_documents({"_id": ctx.author.id, "card_inventory": {"$in": [card]}}) > 0
          usercol.update_one({"_id": ctx.author.id}, {
            "$push": {"card_inventory": card}
          }, upsert=True)
          dupecount = GetUserAttr(ctx.author.id, "card_inventory").count(card)
          embed = discord.Embed()
          embed.description = f'<:shibacheer:720961100375523369> You merged `{requiredcards}` `{tradecards.rarities[mergerarity]}` cards into one:\n{tradecards.rarity_emojis[cardobj["rarity"]]} [`{tradecards.rarities[cardobj["rarity"]]}` **{cardobj["name"]}**](https://duckduckgo.com "You received this card")\n\n*{sanitize(cardobj["quote"])}*' + (f"\n\nDuplicate card! **{dupecount}x**" if duplicate else "")
          embed.set_image(url="attachment://tradecard.png")
          embed.colour = tradecards.rarity_colours[cardobj["rarity"]]
          await ctx.send(ctx.author.mention, file=LoadTradecardImage(card), embed=embed)
          break
        cards = GetUserAttr(ctx.author.id, "card_inventory") or []
        fixed = {}
        for card in cards:
          if card in fixed:
            continue
          fixed[card] = cards.count(card)
        for ccard in chosencards:
          fixed[ccard] -= 1
        embed = discord.Embed()
        embed.title = "Merging cards"
        embed.description = f"Select **`{requiredcards - len(chosencards)}`** more `{tradecards.rarities[mergerarity]}` cards to merge.\n\nChoose one of:\n"
        availcards = 0
        for card in fixed:
          if fixed[card] > 0 and tradecards.tradecards[card]["rarity"] == mergerarity:
            availcards += fixed[card]
            embed.description += f'[`{tradecards.tradecards[card]["name"]}`](https://duckduckgo.com "Type a card\'s name to merge it") (**{fixed[card]}x**) '
        embed.description += "\n\nType `cancel` to cancel the card merge."
        if availcards < requiredcards - len(chosencards):
          await ctx.send(f"You don't have enough `{tradecards.rarities[mergerarity]}` cards to merge them.\nYou need `{requiredcards}` but you only have `{availcards}`.")
          break
        embed.colour = 0x0b5935
        ccmsg = await ctx.send(ctx.author.mention, embed=embed)
        try:
          m = await bot.wait_for("message", timeout=2 * 60, check=check)
        except asyncio.TimeoutError:
          await ccmsg.delete()
          await ctx.send("Timed out while waiting for you to type cards to merge.")
        else:
          await ccmsg.delete()
          await m.delete()
          m = m.content.lower()
          if m == "cancel":
            await ctx.send("Canceled merge.")
            break
          card = None
          cardid = None
          i = 0
          for tcard in tradecards.tradecards:
            if easyfy(tcard["name"]) == easyfy(m):
              card = tcard
              cardid = i
              break
            i += 1
          if card is None:
            await ctx.send("A card by that name does not exist.")
            continue
          if not cardid in fixed or fixed[cardid] == 0:
            await ctx.send("You don't own that card (or it has already been used to merge).")
            continue
          chosencards.append(cardid)



@bot.command(aliases=["sell", "selltradecard"])
async def sellcard(ctx, *, cardname=None):
    if cardname is None:
      await ctx.send("You have to provide a card to sell!")
      return
    card = None
    cardid = None
    i = 0
    for tcard in tradecards.tradecards:
      if easyfy(tcard["name"]) == easyfy(cardname):
        card = tcard
        cardid = i
        break
      i += 1
    if card is None:
      await ctx.send("A card with that name does not exist!")
      return
    owncards = GetUserAttr(ctx.author.id, "card_inventory") or []
    if not cardid in owncards:
      await ctx.send("You don't have that card!")
      return
    sellfor = tradecards.rarity_sellfor[card["rarity"]]
    cmsg = await ctx.send(f'{ctx.author.mention}\nAre you sure that you want to sell one {tradecards.rarity_emojis[card["rarity"]]} `{tradecards.rarities[card["rarity"]]}` `{card["name"]}` card in exchange for `{sellfor:,d}` coins?\nType `yes` or `no`.')
    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
      await cmsg.delete()
      await ctx.send("Timed out while waiting for response.")
    else:
      await cmsg.delete()
      await m.delete()
      m = m.content.lower()
      if m == "yes":
        owncards.remove(cardid)
        SetUserAttr(ctx.author.id, "card_inventory", owncards)
        AddUserCoins(ctx.author.id, sellfor)
        await ctx.send(f'{ctx.author.mention}\nYou sold your {tradecards.rarity_emojis[card["rarity"]]} `{tradecards.rarities[card["rarity"]]}` `{card["name"]}` for `{sellfor:,d}` coins!')
      elif m == "no":
        await ctx.send("Your card was not sold.")
      else:
        await ctx.send("Unknown response. Nothing happened.")


@bot.command(aliases=["cardtrade"])
@level_restrict(15)
async def trade(ctx, user: discord.Member=None):
    if user is None:
      await ctx.send("You must provide a member that you want to trade with!")
      return
    if user.id == ctx.author.id:
      await ctx.send("You thought you could trade with yourself?")
      return
    if user.bot:
      await ctx.send("You cannot trade with bots!")
      return
    inventory = [GetUserAttr(ctx.author.id, "card_inventory") or [], GetUserAttr(user.id, "card_inventory") or []]
    if inventory == [[], []]:
      #no one of the traders own any cards
      await ctx.send("You cannot trade because neither you or the person you want to trade with own any cards.")
      return
    cmsg = await ctx.send(f"Hello, {user.mention}!\n{ctx.author.mention} wants to trade cards with you.\nRespond by typing `yes` or `no` within the next 5 minutes, otherwise the trade will be canceled.")
    def checkr(m):
      return m.author.id == user.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=5 * 60, check=checkr)
    except asyncio.TimeoutError:
      await cmsg.delete()
      await ctx.send(f"Sorry, {ctx.author.mention}. The person you wanted to trade with did not respond in time.")
    else:
      await cmsg.delete()
      await m.delete()
      m = m.content.lower()
      if m == "yes":
        tmsg = await ctx.send("Setting up the trade, please wait...")
        # trader status types:
        # 0 - Not ready (can change their cards)
        # 1 - Ready (has confirmed their input as well as the other trader's input)
        trades = [{"coins": 0, "cards": {}, "status": 0}, {"coins": 0, "cards": {}, "status": 0}]
        async def updmsg():
          embed = discord.Embed()
          embed.title = "Trade!"
          embed.description = f"{ctx.author.mention} and {user.mention} are trading cards.\nType `<amount> <card name>` to set how many of a card you want in the trade (put `0` to remove it).\nTo confirm the trade, type `ready`. If you want to cancel the trade, type `cancel`.\nIf you want to set your coin offer, just type the amount of coins you want to set it to.\nTo talk with your trader, use an underscore (`_`) in the beginning of the message."
          i = 0
          for trader in trades:
            deck = f'Coins: `{trader["coins"]:,d}`\n'
            for card in trader["cards"]:
              deck += f'\n**{trader["cards"][card]}x** [{tradecards.tradecards[card]["name"]}](https://duckduckgo.com "Card name")'
            deck += f'\n**[{"✓ Ready" if trader["status"] == 1 else "🞬 Not ready"}](https://duckduckgo.com "Status")**'
            embed.add_field(name=ctx.author.name if i == 0 else user.name, value=deck)
            i += 1
          embed.colour = 0x3a1131
          await tmsg.edit(content=f"{ctx.author.mention}{user.mention}", embed=embed)
        await updmsg()
        def checkt(m):
          return m.author.id in [ctx.author.id, user.id] and m.channel.id == ctx.channel.id
        while True:
          try:
            c = await bot.wait_for("message", timeout=4 * 60, check=checkt)
          except asyncio.TimeoutError:
            await tmsg.delete()
            await ctx.send(f"{ctx.author.mention}{user.mention}\nOops! Trade was idle for 4 minutes so it was canceled.")
          else:
            await c.delete()
            requester = 0 if c.author.id == ctx.author.id else 1
            req = c.content.lower()
            if req.startswith("_"):
              await ctx.send(f"**{c.author.name}**: {c.content[1:]}")
            elif req in ["clear", "reset", "empty"]:
              trades[requester] = {"coins": 0, "cards": {}, "status": 0}
            elif req in ["ready", "done", "confirm", "ok"]:
              tc = 0
              for trader in trades:
                tc += len(trader["cards"])
              if tc == 0:
                await ctx.send(f"{c.author.mention} You cannot confirm the trade yet! At least one trader must input a card to trade.")
              else:
                trades[requester]["status"] = 1
                if trades[0]["status"] == 1 and trades[1]["status"] == 1:
                  await tmsg.delete()
                  #Both are ready, process trade:
                  #Check if traded things do really exist, in case someone is smart and tries to cheat the system
                  i = 0
                  for trader in trades:
                    tid = ctx.author.id if i == 0 else user.id
                    current_inv = GetUserAttr(tid, "card_inventory") or []
                    if GetUserCoins(tid) < trader["coins"]:
                      await ctx.send(f"{ctx.author.mention}{user.mention}\n**Could not trade!** It seems that someone's trade's input of coins exceeded their current balance.")
                      return
                    for card in trader["cards"]:
                      if not card in current_inv or current_inv.count(card) < trader["cards"][card]:
                        await ctx.send(f"{ctx.author.mention}{user.mention}\n**Could not trade!** It seems that someone's trade did not match their new card inventory.\nThis can happen if someone sells their card after they have added that card to this trade, possibly in attempt to cheat.")
                        return
                    i += 1
                  tidx = 0
                  ninv = [GetUserAttr(ctx.author.id, "card_inventory") or [], GetUserAttr(user.id, "card_inventory") or []]
                  for ftrader in trades:
                    opp = 1 if tidx == 0 else 0
                    item_from = ctx.author.id if tidx == 0 else user.id
                    item_to = user.id if tidx == 0 else ctx.author.id
                    if ftrader["coins"] > 0:
                      TakeUserCoins(item_from, ftrader["coins"])
                      AddUserCoins(item_to, ftrader["coins"])
                    for card in ftrader["cards"]:
                      count = ftrader["cards"][card]
                      for i in range(count):
                        del ninv[tidx][ninv[tidx].index(card)]
                      ninv[opp] += count * [card]
                    tidx += 1
                  SetUserAttr(ctx.author.id, "card_inventory", ninv[0])
                  SetUserAttr(user.id, "card_inventory", ninv[1])
                  await AddExperience(ctx, ctx.author.id, 500)
                  await AddExperience(ctx, user.id, 500)
                  await ctx.send(f"{ctx.author.mention}{user.mention}\nThe trade was successful!")
                  return
            elif req in ["cancel", "exit"]:
              await tmsg.delete()
              await ctx.send(f"{ctx.author.mention}{user.mention}\nThe trade was canceled by {c.author.mention}.")
              return
            else:
              parts = req.split(" ", 1)
              if len(parts) > 1:
                if parts[0].isnumeric():
                  cardamount = int(parts[0])
                  card = None
                  cardid = None
                  i = 0
                  for tcard in tradecards.tradecards:
                    if easyfy(tcard["name"]) == easyfy(parts[1]):
                      card = tcard
                      cardid = i
                      break
                    i += 1
                  if card is None:
                    await ctx.send(f"{c.author.mention} Such card does not exist!")
                  else:
                    if not cardid in inventory[requester]:
                      await ctx.send(f"{c.author.mention} You don't own that card!")
                    else:
                      if cardamount > inventory[requester].count(cardid):
                        await ctx.send(f"{c.author.mention} You don't have that many of that card.")
                      else:
                        if len(trades[requester]["cards"]) + cardamount > 25:
                          await ctx.send(f"{c.author.mention} Max 25 cards per trader!")
                        else:
                          trades[0]["status"] = 0
                          trades[1]["status"] = 0
                          if cardamount == 0:
                            if cardid in trades[requester]["cards"]:
                              del trades[requester]["cards"][cardid]
                          else:
                            trades[requester]["cards"][cardid] = cardamount
                else:
                  await ctx.send(f"{c.author.mention} Invalid request.")
              else:
                if parts[0].isnumeric():
                  coinoffer = int(parts[0])
                  if coinoffer > GetUserCoins(c.author.id):
                    await ctx.send(f"{c.author.mention} You don't have that many coins!")
                  else:
                    if coinoffer > 100000:
                      await ctx.send(f"{c.author.mention} You can't offer more than `100,000` coins!")
                    else:
                      trades[0]["status"] = 0
                      trades[1]["status"] = 0
                      trades[requester]["coins"] = coinoffer
                else:
                  await ctx.send(f"{c.author.mention} Invalid request. Type e.g. `1 Pop cat` to add a card to the trade or just type e.g. `150` to set your coin offer to `150`.")
            await updmsg()
      elif m == "no":
        await ctx.send(f"{user.mention}\nYou did not want to trade with {ctx.author.mention}.")
      else:
        await ctx.send(f"{user.mention}\nThat was not a valid response and the trade with {ctx.author.mention} was canceled.")


@bot.command(aliases=["myroles", "temporaryroles"])
async def roles(ctx):
    troles = temprolescol.find({"user": ctx.author.id}) or []
    aroles = []
    for trole in troles:
      aroles.append([
        discord.utils.get(bot.guilds[0].roles, id=trole.get("role")),
        trole.get("expires")
      ])
    embed = discord.Embed()
    embed.title = "Study Fam Temporary Roles"
    embed.description = "These are your roles that you have purchased from the shop that are going to expire.\n"
    if len(aroles) == 0:
      embed.description += "\nNo temporary roles."
    else:
      for role in aroles:
        embed.description += f"\n{role[0].mention}: Expires in **[{GetTimeString(role[1] - time.time())}](https://duckduckgo.com \"Temporary role expires\")**"
    embed.colour = 0xf47c3f
    embed.set_thumbnail(url="https://i.imgur.com/zHwbaVS.png")
    await ctx.send(embed=embed)




@bot.command()
@debugging_only()
async def error(ctx):
    raise Exception




async def SelfDestruction(message):
    if message.channel.id != channels.BotCommands:
      await message.reply("Seems like you found our secret code sentence for self-destruction. But you can't do it in here, you have to be in the bot commands channel.")
      return
    def checkdm(m):
      return m.author.id == message.author.id
    cmsg = await message.reply("Do you really want to destroy your last messages in this channel\nType `no ragrets` to continue.")
    def check(m):
      return m.author.id == message.author.id and m.channel.id == message.channel.id
    try:
      m = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
      await cmsg.delete()
      await message.delete()
      await message.channel.send("Timed out. Now you won't have any regrets!")
    else:
      await m.delete()
      await cmsg.delete()
      await message.delete()
      m = m.content.lower()
      if m == "no ragrets":
        chickengif = await message.channel.send("https://tenor.com/view/chicken-chicken-bro-destroy-boom-explosion-gif-14109606")
        await asyncio.sleep(2)
        await chickengif.delete()
        wmsg = await message.channel.send("Your messages are being deleted, please remain calm...")
        amount = await message.channel.purge(limit=50, check=checkdm)
        await wmsg.delete()
        await message.channel.send(f"{message.author.mention} Your last {len(amount)} messages have been deleted successfully.", delete_after=30)
      else:
        await message.channel.send(f"{message.author.mention} You did not confirm! No regrets this time.", delete_after=15)



@bot.command(aliases=["t", "tr", "translation", "trans"])
@level_restrict(3)
async def translate(ctx, fromlang=None, tolang=None, *, text=None):
    if fromlang is None:
      await ctx.send("You must provide a language of the text that you want to translate (english, french etc.). Put `auto` to automatically detect the language.")
      return
    if tolang is None:
      await ctx.send("You must provide a language to translate into.")
      return
    if text is None:
      await ctx.send("You must provide a text to translate!")
      return
    fromlang = fromlang.lower()
    tolang = tolang.lower()
    if fromlang == tolang:
      await ctx.send("You cannot translate into the same language! What are you thinking?")
      return
    langs = GoogleTranslator.get_supported_languages()
    for clang in [fromlang, tolang]:
      if clang not in langs and clang != "auto":
        await ctx.send(f'The language `{sanitize(clang)}` is not supported. Make sure that it is fully spelled and not an abbreviation.\nThe supported languages are:\n`{", ".join(langs)}`')
        return
    translation = GoogleTranslator(source=fromlang, target=tolang).translate(text)
    embed = discord.Embed()
    embed.set_author(name=f"{fromlang.upper()} ➔ {tolang.upper()}")
    embed.title = "Translation"
    embed.add_field(name=fromlang.upper(), value=sanitize(text))
    embed.add_field(name=tolang.upper(), value=f"[{sanitize(translation)}](https://duckduckgo.com \"Translated into this\")")
    embed.colour = 0x6d8409
    await ctx.send(ctx.author.mention, embed=embed)

@bot.command()
@debugging_only()
async def speak(ctx, *, text=None):
    await ctx.message.delete()
    await ctx.send(text or "unknown...")


@bot.command(aliases=["sw", "watch"])
async def stopwatch(ctx, action=None):
    settings = GetUserAttr(ctx.author.id, "stopwatch") or {
      "begin": None,
      "pause": None,
      "remove": 0
    }
    if action in ["start", "begin", "continue"]:
      if settings["begin"] is None and settings["pause"] is None:
        settings["begin"] = time.time()
        await ctx.send("Started stopwatch!")
      elif settings["pause"] is not None:
        settings["remove"] += time.time() - settings["pause"]
        settings["pause"] = None
        await ctx.send("Continued stopwatch.")
      else:
        await ctx.send("You cannot start the stopwatch right now because it's already running. The timer must either be paused or not active to be started.")
    elif action in ["stop", "end"]:
      if settings["begin"] is not None:
        if settings["pause"] is not None:
          settings["remove"] += time.time() - settings["pause"]
          settings["pause"] = None
        await ctx.send(embed=discord.Embed(
          title="Stopwatch has ended",
          description=f'You stopped your stopwatch.\nStopwatch took [**`{GetTimeString(time.time() - settings["begin"] - settings["remove"])}`**](https://duckduckgo.com "Stopwatch took this long").',
          colour=0x96213a
        ))
        settings["begin"] = None
      else:
        await ctx.send("Your stopwatch is not active, therefore you cannot stop it.")
    elif action in ["pause"]:
      if settings["begin"] is not None and settings["pause"] is None:
        settings["pause"] = time.time()
        await ctx.send("Your stopwatch has been paused.")
      elif settings["pause"] is not None:
        await ctx.send("Your stopwatch is already paused.")
      else:
        await ctx.send("Your stopwatch is not active so you cannot pause it.")
    elif action in [None, "info", "help"]:
      if settings["begin"] is None:
        await ctx.send("Your stopwatch is not active.\nDo `mom stopwatch start` to start the stopwatch.")
      else:
        await ctx.send(embed=discord.Embed(
          description=("**Stopwatch is paused**\n" if settings["pause"] is not None else f'Stopwatch has taken [**`{GetTimeString(time.time() - settings["begin"] - settings["remove"])}`**](https://duckduckgo.com "Stopwatch has taken this long so far").\n') + f'Stopwatch was started `{GetTimeString(time.time() - settings["begin"])}` ago.\n\nUse `mom stopwatch stop` to end the stopwatch or `mom stopwatch pause`/`mom stopwatch continue` to pause it or continue it.',
          colour=0x29213f
        ))


    if settings["begin"] is not None:
      SetUserAttr(ctx.author.id, "stopwatch", settings)
    else:
      RemUserAttr(ctx.author.id, "stopwatch")


@bot.command(aliases=["nodistract", "undistract", "nd"])
async def togglenodistract(ctx):
    frole = discord.utils.get(bot.guilds[0].roles, id=783777725487382570)
    hasrole = frole in ctx.author.roles
    if hasrole:
      await ctx.author.remove_roles(frole)
      await ctx.send("<:Check:783760461556350986> Enabled no-distraction mode\nHappy studying!")
    else:
      await ctx.author.add_roles(frole)
      await ctx.send("<:Cross:783760537967394836> Disabled no-distraction mode\n__You can now see the whole server!__")


@bot.command()
async def invite(ctx):
    if len(GetUserAttr(ctx.author.id, "invite_list") or []) >= 5:
      await ctx.send("Oh no! You have already invited 5 people and you cannot invite anyone else with this command. Please use the global server invite link instead by clicking \"Study Fam\" and then \"Invite People\".")
    elif invcol.find_one({"inviteowner": ctx.author.id}) is None:
      theinvite = await ctx.channel.create_invite(max_uses=1)
      invcol.insert_one({"inviteowner": ctx.author.id, "url": theinvite.url, "code": theinvite.code})
      await ctx.send("Your invite has been created!\nShare this invite with someone and earn some coins when they use it: " + theinvite.url)
    else:
      await ctx.send("You already have an active invite, your invite is: " + invcol.find_one({"inviteowner": ctx.author.id}).get("url"))

# @bot.command()
# @admin_only()
# async def amelia(ctx):
#     inv = GetUserAttr(cardauthors.amelia, "card_inventory") or []
#     i = 0
#     for thecard in tradecards.tradecards:
#       if thecard["author"] == cardauthors.amelia:
#         inv.append(i)
#       i += 1
#     SetUserAttr(cardauthors.amelia, "card_inventory", inv)
#     await ctx.send("amelia got her cards!")

@bot.command(aliases=["message", "anonymous", "a"])
async def anon(ctx, *, message=None):
  if ctx.channel.id not in [
    720769667542679684
    # add more channels here to allow anonymous messages in
  ]:
    await ctx.message.delete()
    await ctx.send(ctx.author.mention + " Sorry, but you can't make anonymous messages here.", delete_after=10)
    return
  if message is None:
    await ctx.send("No message was provided!")
    return
  def generatecode(iter=0):
    if iter >= 60:
      return 0
    tcode = random.randint(100, 999)
    return tcode if anoncol.count_documents({"code": tcode}) == 0 else generatecode(iter + 1)
  code = generatecode()
  if code == 0:
    await ctx.send("Sorry, could not generate a valid code.")
    return
  await ctx.message.delete()
  embed = discord.Embed()
  embed.set_author(name="Anonymous #" + str(code), icon_url="https://icons.iconarchive.com/icons/flameia/xrabbit/128/Tools-Terminal-icon.png")#"https://icons.iconarchive.com/icons/pixelmixer/basic-2/32/user-anonymous-icon.png")
  embed.description = sanitize(message)
  embed.colour = 0x2f3136
  replyto = ctx.message.reference
  if replyto is None:
    msg = await ctx.send(embed=embed)
  else:
    msgreply = await ctx.fetch_message(replyto.message_id)
    msg = await msgreply.reply(embed=embed)
  anoncol.insert_one({
    "_id": msg.id,
    "code": code,
    "author": ctx.author.id,
    "message": message
  })

@bot.command()
@admin_only()
async def checkanon(ctx):
  if ctx.message.reference is None:
    await ctx.send("To check the author of an anonymous message, you must reply to that message with this command.")
    return
  amid = ctx.message.reference.message_id
  anondoc = anoncol.find_one({"_id": amid})
  if anondoc is None:
    await ctx.send("Sorry, the message cannot be linked to the database!")
    return
  author = bot.guilds[0].get_member(anondoc.get("author"))
  try:
    await ctx.author.send(author.name + " (" + str(author.id) + ") wrote that message.")
    await ctx.message.delete()
  except:
    await ctx.send("Could not DM you.")

@bot.command()
async def delanon(ctx):
  if ctx.message.reference is None:
    await ctx.send("To delete an anonymous message, you must reply to that message with this command.")
    return
  amid = ctx.message.reference.message_id
  anondoc = anoncol.find_one({"_id": amid})
  if anondoc is None:
    await ctx.send("Sorry, the message cannot be linked to the database!")
    return
  if anondoc.get("author") == ctx.author.id or ctx.author.id in whitelist.admins:
    anoncol.delete_one({"_id": amid})
    msg = await ctx.fetch_message(amid)
    newembed = msg.embeds[0]
    newembed.description = "[Removed by " + ("the author" if anondoc.get("author") == ctx.author.id else "an admin") + "]"
    await msg.edit(embed=newembed)
    tempmsg = await ctx.send("The anonymous message was deleted.")
    await asyncio.sleep(5)
    await ctx.message.delete()
    await tempmsg.delete()
  else:
    await ctx.send("You're not allowed to delete that!")

@bot.command()
@debugging_only("waiting for release")
async def vote(ctx, *, text=None):
    if votecol.count_documents({"author": ctx.author.id, "active": True}) >= 3:
      await ctx.send("You already have 3 active votes. Please close one before creating another.")
      return
    if text is None:
      await ctx.send("You need to provide a text for context. Please try again.")
      return
    if len(text) > 200:
      await ctx.send("Max 200 characters! Try again.")
      return
    def generatecode(iter=0):
      if iter >= 60:
        return 0
      tcode = random.randint(100, 999)
      return tcode if votecol.count_documents({"code": tcode}) == 0 else generatecode(iter + 1)
    code = generatecode()
    if code == 0:
      await ctx.send("Sorry, could not generate a valid code.")
      return
    message = await ctx.send("Creating vote, please wait...")
    votetypes = ["👍", "👎", "✅"]
    for i in votetypes:
      await message.add_reaction(i)
    votecol.insert_one({
      "code": code,
      "author": ctx.author.id,
      "created": time.time(),
      "text": text,
      "message": message.id,
      "votes": {},
      "active": True
    })
    await UpdateVoteMessage(message)
    await ctx.message.delete()

@bot.command()
@debugging_only()
async def debugubt(ctx):
    await UpdateBroadcastTexts(force=True)
    await ctx.send("Success")

@bot.command(aliases=["studying", "whostudy"])
async def studylist(ctx):
  embed = discord.Embed()
  embed.title = "Studying Members"
  desc = "Currently **" + str(studycol.count_documents({})) + "** people studying."
  for studying in studycol.find({}):
    member = bot.guilds[0].get_member(studying.get("_id"))
    desc += "\n" + member.mention + " - **" + GetTimeString(time.time() - studying.get("study_begin")) + "**"
  embed.description = desc
  embed.colour = 0x3f528c
  embed.set_thumbnail(url=bot.guilds[0].get_member(studycol.find_one({}).get("_id")).avatar_url_as(size=64))
  await ctx.send(embed=embed)

@bot.command()
async def type(ctx):
  await ctx.message.delete()
  async with ctx.typing():
    await asyncio.sleep(10)

bot.run(os.getenv("DISCORD_TOKEN"))