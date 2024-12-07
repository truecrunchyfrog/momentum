import os, pymongo, time, datetime, asyncio, random, math, requests, sys, hashlib, flag, re
import discord
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
from babel import Locale
import settings.channels as channels
import settings.sounds as sounds
import settings.presets as presets
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
studybuddiescol = userdatabase["studybuddies"]
buddytrackingcol = userdatabase["buddytracking"]
matchchanscol = metadatabase["matchchans"]
vcrolescol = metadatabase["vcroles"]
sessionarchivecol = metadatabase["sessionarchive"]
weeklystatscol = userdatabase["weekly"]
foreignlangusagecol = userdatabase["langusage"]

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
    xp = GetUserAttr(uid, "experience") or 0
    requiredxp = 0
    i = 0
    while True:
      reqxplevel = math.floor(((i + 5) ** 4))#math.floor(((i + 5) ** 3) / 3)
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

class WaitTaskMsg:
  def __init__(self, chan: discord.abc.Messageable, text):
    self.chan = chan
    self.text = text
    self.message = None
  async def build(self):
    self.message = await self.chan.send(f"<a:Waiting_for_this_task_to_finish:938200044992102500>  {self.text or 'Please wait...'}")
  async def dispose(self):
    if self.message:
      await self.message.delete()
    else:
      raise Exception("Task wait message was never built!")



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

def enhash(string):
    return hashlib.md5(bytes(string, "utf-8")).hexdigest()

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
      try:
        lastactivitymsg = await bot.get_channel(channels.BotCommands).fetch_message(lastactivitymsgid)
      except discord.errors.NotFound:
        lastactivitymsg = None
      if lastactivitymsg is not None:
        await lastactivitymsg.delete()
    activitybackmsg = await bot.get_channel(channels.BotCommands).send("\🍰 " + random.choice([
      "Momentum is back up again.",
      "Return of the bot!",
      "I'm here again.",
      "Thank you for your patience.",
      "Back to serving.",
      "I'm back now."
    ]))
    botactivitycol.update_one({"_id": 0}, {"$set": {"lastactive": time.time(), "lastmessage": activitybackmsg.id}}, upsert=True)

    os.system("clear")
    print("Discord authentication ready")
    for i in levelroles:
      levelroles[i] = discord.utils.get(bot.guilds[0].roles, id=levelroles[i])
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
    asyncio.get_event_loop().create_task(rl_loop())
    asyncio.get_event_loop().create_task(mc_loop())
    asyncio.get_event_loop().create_task(ku_loop())
    asyncio.get_event_loop().create_task(LoadTimers())
    await CompareDatabase()
    await ConfirmVCRoles()
    if botactivitycol.count_documents({"_id": 1}) > 0:
      doc = botactivitycol.find_one({"_id": 1})
      await bot.guilds[0].get_channel(doc.get("reboot_chan")).send(f"Reboot complete. Took {GetTimeString(time.time() - doc.get('timestamp'))}.")
      botactivitycol.delete_one({"_id": 1})

async def UpdateStatus():
    studycount = studycol.count_documents({})
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'{studycount} {"people" if studycount != 1 else "person"} study'), status=discord.Status.idle)

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
    return
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

async def CheckCamMembers():
    voicestates = bot.get_channel(channels.VCCamOn).voice_states
    for voicemap in list(voicestates.items()):
      doc = studycol.find_one({"_id": voicemap[0]})
      if doc is not None:
        if not voicemap[1].self_video and time.time() - doc.get("study_begin") > 60:
          member = bot.guilds[0].get_member(voicemap[0])
          await member.move_to(None)
          try:
            #https://cdn.discordapp.com/attachments/802215570996330517/969318331628810340/New_Project.png
            embed = discord.Embed()
            embed.title = "🩴 Kicked from camera channel"
            embed.description = "You have been kicked from this voice channel for not participating with your camera.\nTo enable your camera, click the `Video` button once you join."
            embed.colour = 0xc14745
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/802215570996330517/969318331628810340/New_Project.png")
            await member.send(embed=embed)
          except:
            pass
          print("Kicked " + member.name + " from the Cam On voice channel.")


#reset leaderboard
async def rl_loop():
    while True:
      await asyncio.sleep(2 * 60)
      await CheckMonthlyLeaderboardReset()


#match channels check
async def mc_loop():
    while True:
      await asyncio.sleep(10 * 60)
      for expired_chan in matchchanscol.find({"expiration": {"$lt": time.time()}}):
        matchchanscol.delete_one({"_id": expired_chan.get("_id")})
        await bot.get_channel(expired_chan.get("channel")).delete()
      for soon_expiring_chan in matchchanscol.find({"expiration": {"$lt": time.time() + 60 * 60}, "deletion_alert_sent": {"$not": {"$eq": True}}}):
        matchchanscol.update_one({"_id": soon_expiring_chan.get("_id")}, {"$set": {"deletion_alert_sent": True}})
        buddy1 = await bot.fetch_user(soon_expiring_chan.get("buddies")[0])
        buddy2 = await bot.fetch_user(soon_expiring_chan.get("buddies")[1])
        await bot.get_channel(soon_expiring_chan.get("channel")).send(buddy1.mention + buddy2.mention + "\nThis is a reminder that this channel will be deleted within less than an hour. If you are planning on becoming study buddies I suggest you take the discussion further somewhere else now if you haven't already.\nGood luck!")

#kick users exceeding 6h of study time
async def ku_loop():
    while True:
      await asyncio.sleep(10 * 60)
      for studying in studycol.find({"study_begin": {"$lt": time.time() - 60 * 60 * 6}}):
        studying = bot.guilds[0].get_member(studying.get("_id"))
        if studying.voice:
          await studying.move_to(None)
          try:
            await studying.send("**Did you fall asleep?** You have been kicked from the study channel for studying in there for more than 6 hours.\nIf you were actually studying, just ignore this message and rejoin.")
          except:
            pass

async def CheckMonthlyLeaderboardReset(force=False):
    idstr = "reset_leaderboard"
    delay = 30.5 * 24 * 60 * 60
    if IsDelayedLoopReady(idstr, delay) or force:
      UpdateLoopUsed(idstr, delay)

      slmsg = await bot.get_channel(channels.BotCommands).send("Saving the leaderboard here...")
      await leaderboard(await bot.get_context(slmsg)) # Print the leaderboard in bot commands

      rquery = {
        "studytokens": {"$gte": 100}
      }
      lbdocne = usercol.find(rquery, {"_id": 1, "studytokens": 1})
      if usercol.count_documents(rquery) == 0:
        await bot.get_channel(channels.News).send("End of month! Huh, nobody is on the leaderboard!?")
        return
      topmemberssorted = lbdocne.sort([("studytokens", -1)])
      n1mem = None
      n2mem = None
      n3mem = None
      for member in topmemberssorted:
        member = bot.guilds[0].get_member(member.get("_id"))
        if member:
          if not n1mem:
            n1mem = member
          elif not n2mem:
            n2mem = member
          elif not n3mem:
            n3mem = member
            break
      if not n3mem:
        return
      winner_role_id = 713478276479451206
      await n1mem.add_roles(discord.utils.get(bot.guilds[0].roles, id=winner_role_id))
      temprolescol.delete_many({ "user": n1mem.id, "role": winner_role_id })
      temprolescol.insert_one({
        "expires": time.time() + delay,
        "role": winner_role_id,
        "user": n1mem.id
      })
      await n1mem.edit(nick="👑 " + n1mem.name)
      n1reward = 15000
      runnersupreward = 8000
      AddUserCoins(n1mem.id, n1reward)
      AddUserCoins(n2mem.id, runnersupreward)
      AddUserCoins(n3mem.id, runnersupreward)
      usercol.update_many({"studytokens": {"$exists": True}}, {"$unset": {"studytokens": ""}})

      embed = discord.Embed()
      embed.title = "<:book:816522587424817183> Monthly Reset"
      #embed.description = f"A new month is here and it's time to reset the leaderboard!\n**Congratulations winners!**\nThese people studied the best last month:\n1st: {n1mem.mention}\n2nd: {n2mem.mention}\n3rd: {n3mem.mention}\n\nThe winner has received 1 month of gold membership and coins. The 2nd and 3rd leaders earned some coins.\n\nMaybe this month is your chance to study well? Good luck people!\n[Click here]({slmsg.jump_url}) to see the archived first leaderboard page."
      embed.description = f"✨ A new month is here, so it's time to congratulate the following three who have topped our leaderboard last month and to continue the succession of the throne! <:kingcat:730063415959224320> Thank you for inspiring us this month with your hard work!\n\n1st: {n1mem.mention}\n2nd: {n2mem.mention}\n3rd: {n3mem.mention}\n🎉 All hail the new monthly leader {n1mem.mention}! The coin rewards have already been deposited into the accounts of the top 3! <:I_got_money:739540510674256005>\n\nGood job as well to ALL frogs this month for the work done <:catpats:913604825479008326>\nAll the best for the next month, we are looking forward to your company!! <:comfyblob:730063563892195408>\n\nAlso, [click here]({slmsg.jump_url}) to see the full first leaderboard page."
      embed.colour = 0xaa763f

      newsfeedrole = discord.utils.get(bot.guilds[0].roles, id=844605574032916512)
      await bot.get_channel(channels.News).send(newsfeedrole.mention + n1mem.mention + n2mem.mention + n3mem.mention, embed=embed)

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

async def ConfirmVCRoles():
    print("Confirming VC roles...")
    for vcrole in vcrolescol.find():
      if bot.guilds[0].get_channel(vcrole.get("channel")) is None:
        try:
          vcrolescol.delete_one({"_id": vcrole.get("_id")})
          await bot.guilds[0].get_role(vcrole.get("role")).delete()
          print("Deleted an obsolete VC role.")
        except:
          print("Could not delete VC role.")
    print("VC roles confirm done.")


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

async def CollectTaxes():
    idstr = "collect_taxes"
    delay = 14 * 24 * 60 * 60
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
        description=f"<:cat_cry_thumbsup:855880898208333824> It's time for taxes!\nCollected `{totalcoinstaken:,d} coins` in total. ([?](https://discord.com/channels/712808127539707927/713177565849845849/801373465546457138 \"Click to see more information about taxes\"))",
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
      embed.description = "Help the server grow by typing `/bump`."
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
        #if someone bumbed
        UpdateLoopUsed("remind_bump", 2 * 60 * 60)
        embed = discord.Embed()
        embed.description = "Thank you for helping out the server!"
        embed.colour = 0x2a7c52
        embed.set_thumbnail(url="https://icons.iconarchive.com/icons/icehouse/smurf/32/Jokeys-present-icon.png")
        await message.channel.send(embed=embed)
        await message.delete()
      return
    if isinstance(message.channel, discord.channel.DMChannel):
      return
    
    c = message.content
    if "@everyone" in c or "@here" in c and "https://" in c or "http://" in c:
      last_suspicious_message = GetUserAttr(message.author.id, "last_suspicious_message")
      if last_suspicious_message is None or last_suspicious_message[2] < time.time() - 60 * 60 * 24:
        SetUserAttr(message.author.id, "last_suspicious_message", [enhash(c), [message.channel.id, message.id], time.time()])
      elif enhash(c) == last_suspicious_message[0]:
        RemUserAttr(message.author.id, "last_suspicious_message")
        chan_msg = last_suspicious_message[1]
        try:
          old_message = await bot.get_channel(chan_msg[0]).fetch_message(chan_msg[1])
          await old_message.delete()
          await message.delete()
        except:
          pass
        try:
          member_role = discord.utils.get(bot.guilds[0].roles, id=713466849148534814)
          full_access_role = discord.utils.get(bot.guilds[0].roles, id=783777725487382570)
          await message.author.remove_roles(member_role, full_access_role)
        except:
          pass
        try:
          await bot.get_channel(channels.StaffOnly).send(f"**CAUTION!** {message.author.mention} (`{message.author.id}`, `{message.author.name}#{message.author.discriminator}`) has been detected for potential spam, they sent the following message multiple times:\n\n```\n{sanitize(c)}\n```\n\nThey have been removed the default roles and have to get verified again to gain access to the channels again. The messages have also been deleted.")
          await message.author.send("**SPAM DETECTION!** You have been temporarily removed (not banned yet) from the server while the staff review the infraction. Please open a ticket to explain if you've done so accidentally.")
        except:
          pass
        return
    if message.channel.id == 748862262793732160 and len(message.attachments) == 1:
      await NewPrestige(message.author.id, "nicememe")
    lc = c.lower()
    if ("sleep" in lc or "to bed" in lc) and len(c) < 40 and (("have to" in lc or "should" in lc or "will" in lc or "now" in lc or "head" in lc or "going to" in lc) and not "soon" in lc and (not "you" in lc or (" i " in lc or " i'" in lc or " im " in lc))):
      async with message.channel.typing():
        await asyncio.sleep(random.randint(4, 8))
        await message.reply(random.choice(["Sleep well {0}! We'll see you later.", "It's been a long day. You deserve a good sleep {0}!", "Well done {0}! Good night!", "Good night mate {0}!", "See you tomorrow {0}!", "Good night {0}! Sleep well!", "You have done well today, as everyday!", "Today was a big day, tomorrow is a big day. You should get some good sleep!", "We all wish you a good night {0}!"]).format(sanitize(message.author.name)))
    if len(c) < 35:
      if "beaver" in lc:
        await message.reply("https://tenor.com/view/baby-beaver-cute-gif-9929643", delete_after=11)
      if "horse" in lc:
        await message.reply("https://tenor.com/view/horse-riding-truck-skid-action-gif-13177019", delete_after=6)
      if "i hate you" in lc:
        await message.reply("https://tenor.com/view/19dollar-fortnite-card-among-us-amogus-sus-red-among-sus-gif-20549014", delete_after=2)
      if "a blast" in lc:
        await message.reply("https://tenor.com/view/duck-swing-playground-cute-gif-16385102", delete_after=6)
      if "turtle" in lc:
        await message.reply("https://tenor.com/view/turtle-gif-7551142", delete_after=3)
      if "that's epic" in lc or "thats epic" in lc:
        await message.reply("https://tenor.com/view/frog-look-stare-gif-15464672", delete_after=2)
      if "amogass" in lc:
        await message.reply("https://tenor.com/view/amongus-amongass-ass-gif-22654532", delete_after=5)
      if "bastu" in lc:
        await message.reply("https://tenor.com/view/capybara-bucket-sit-spa-capybara-bucket-gif-23305453", delete_after=16)
    for mentioned in message.mentions:
      if mentioned.id == 195258903368302592:
        if message.author.id == 645627385542344704:
          await message.author.send("<:ping:926132029697982564>")
        else:
          await message.add_reaction("<:ping:926132029697982564>")
    if (("mom" in lc or "beaver" in lc) and len(lc) < 80 and ("you" in lc or " u " in lc or "u'" in lc or " ur " in lc or " go " in lc) and ("work" in lc or "slave" in lc or "poor" in lc or "suck" in lc or "bad" in lc or "i hate" in lc or "terrible" in lc or "stink" in lc or "die" in lc or "ugly" in lc or "annoying" in lc)):
      SetUserAttr(message.author.id, "toxicity", time.time())
      await message.channel.send("You gotta do what you gotta do.")
      return
    if lc == "no regrets":
      await SelfDestruction(message)
    if message.content == f"<@{bot.user.id}>":
      await message.reply("For help, type `mom help`.")
    if lc.startswith("pls ") and message.channel.id == channels.BotCommands:
      await message.reply(f"Please use Dank Memer commands in {bot.get_channel(channels.DankMemer).mention}.")
    if not lc.startswith("mom "):
      if random.randrange(0, 2) == 0:
        await AddExperience(message.channel, message.author.id, 15)
      # give study tokens for sending messages in "music study chat"
      if message.channel.id == 722880141134397460 and random.randrange(0, 2) == 0:
        AddUserTokens(message.author.id, 1)

      if message.reference is not None: # Reply to anon
        mid = message.reference.message_id
        anondoc = anoncol.find_one({"_id": mid})
        if anondoc is not None and anondoc.get("author") != message.author.id:
          anonauthor = bot.guilds[0].get_member(anondoc.get("author"))
          try:
            await anonauthor.send(sanitize(message.author.name) + " replied to your anonymous message: " + message.jump_url)
          except:
            pass

    if message.channel.id == 725451170604384308 and not (GetUserAttr(message.author.id, "dca") or False):
      await message.delete()
      conf = await message.channel.send(message.author.mention + " You sure you wanna chat here?")
      await conf.add_reaction("👍")
      def check(reaction, user):
        return user.id == message.author.id and reaction.message.id == message.id and reaction.emoji == "👍"
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
    await MemberCheck(member)
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
        AddUserCoins(inviter.id, 300)
        try:
          await inviter.send("Thank you for inviting " + sanitize(member.name) + " to Study Fam! You have been given <:famcoin2:845382244554113064> `300`.")
        except:
          pass
        # don't break the loop here, to allow previous invites to be cleared as well, if they were removed while the bot was offline
    print(member.name + " joined the server!")
    embed = discord.Embed()
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{member.id}/{member.avatar}.png?size=64")
    embed.description = f"\n{random.choice(joinmessages.emojis)} " + (random.choice(joinmessages.messages).format(f"[{sanitize(member.name)}#{member.discriminator}](https://discord.com/channels/@me/{member.id} \"That's great!\")")) + f"\n\nMember #{bot.guilds[0].member_count}"
    embed.colour = 0x2f3136
    await bot.get_channel(channels.General).send(embed=embed, delete_after=5 * 60)

@bot.event
async def on_member_update(before, after):
    await asyncio.sleep(1)
    await MemberCheck(after)

async def MemberCheck(member):
    old_nick = member.nick or member.name
    if not re.match(r".*([A-z]|[0-9])([A-z]|[0-9]).*", old_nick):
      funny_prefixes = ["Studying", "Study", "Fantastic", "Great", "Awesome", "Nice", "Crunchy", "Crazy", "Grumpy", "Fabulous", "Fancy", "Happy", "Sad", "Friendly", "Laughing", "Crying", "Good", "Sobbing", "Koala"]
      funny_suffixes = ["Frog", "Turtle", "Dragon", "Fox", "Gru", "Grandma", "Student", "Orange", "Kiwi", "Banana", "Rat", "Fam"]
      new_nick = random.choice(funny_prefixes) + random.choice(funny_suffixes)
      await member.edit(nick=new_nick)
      print(f"Changed nickname that does not meet requirements! ({old_nick} -> {new_nick})")
      try:
        await member.send(f"Hello there! I've run a check and it appears that your nickname in the Study Fam server did not match our requirement of 2 consecutive Latin letters. A placeholder has thus been temporarily assigned. You are encouraged to change it as long as they meet the requirement!\n\nYour old nickname that did not meet the requirements was `{old_nick}`,\nand your new placeholder nickname is `{new_nick}`.")
      except:
        pass

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
      return
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
        await bot.get_channel(channels.BotCommands).send(f"{payload.member.mention} You tried to star a message, but I couldn't deliver the message to you. Please enable \"Direct Messages\" in your privacy settings, just temporarily if you want, while you do this.")
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
              embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.with_size(32).url)
              sendfiles = []
              if len(message.attachments) == 0:
                content = message.content
                if len(message.embeds) > 0:
                  content = message.embeds[0].description
                embed.description = content or "..."
              else:
                for attc in message.attachments:
                  sendfiles.append(await attc.to_file())
                ac = len(message.attachments)
                embed.description = str(ac) + " attachment" + ("s" if ac != 1 else "")
              embed.description += f"\n\n[\🐸 Hop to the source]({message.jump_url} \"More like hop to the pond but this I guess this may be interpreted better\") (posted <t:{int(message.created_at.timestamp())}:R> in {message.channel.mention})"
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
    if payload.emoji.name == "🗑️" and matchchanscol.count_documents({"message": payload.message_id}) > 0:
      chan = bot.get_channel(payload.channel_id)
      await (await chan.fetch_message(payload.message_id)).remove_reaction(payload.emoji, payload.member)
      cmsg = await chan.send(payload.member.mention + "\nAre you sure that you want to dispose this channel now?\nRespond with `yes` or `no`!")
      responses = ["yes", "no"]
      def check(m):
        return m.channel.id == payload.channel_id and m.author.id == payload.member.id and m.content.lower() in responses
      try:
        m = await bot.wait_for("message", timeout=30, check=check)
      except:
        await cmsg.delete()
      else:
        await cmsg.delete()
        await m.delete()
        if responses.index(m.content.lower()) == 0:
          wmsg = WaitTaskMsg(chan, "The channel is being deleted, please wait...")
          await wmsg.build()
          await asyncio.sleep(10)
          await chan.delete()
          matchchanscol.delete_one({"message": payload.message_id})
        else:
          await chan.send("Canceled, the channel has not been deleted!", delete_after=10)
    if payload.emoji.name == "🩲" and payload.member.id in whitelist.admins:
      chan = bot.get_channel(payload.channel_id)
      await (await chan.fetch_message(payload.message_id)).delete()


lasterror = 0

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("Expected a member.")
    elif isinstance(error, commands.CommandNotFound):
      await ctx.send(embed=discord.Embed(
        description=f"<a:thisisfine:856617800395259904> Sorry! No such command: [`{sanitize(ctx.invoked_with)}`](https://.) could be found.\nRun `mom help` and see if you can find what you are looking for.\nYou can also ask staff to help you find it.",
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
      embed.description = f"<a:thisisfine:856617800395259904> Sorry!\nAn error occured while trying to run your command: `{sanitize(ctx.invoked_with)}`.\nAlert the developer by clicking the check icon below.\n**Debug information:**\n```\n{error}```"
      embed.colour = 0x2f3136
      embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/861542071905943562/890874808412291092/image.png")
      emsg = await ctx.send(embed=embed)
      await emsg.add_reaction("<:Check:783760461556350986>")
      def check(reaction, user):
        return user.id == ctx.author.id and reaction.message.id == emsg.id and reaction.emoji.id == 783760461556350986
      try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
      except asyncio.TimeoutError:
        await emsg.remove_reaction("<:Check:783760461556350986>", bot.user)
      else:
        await emsg.clear_reaction("<:Check:783760461556350986>")
        await emsg.remove_reaction("<:Check:783760461556350986>", ctx.author)
        await emsg.reply("<@&829737618018140180>")
      raise error


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
      return
    using_cam = False
    if member.voice is not None and (member.voice.self_stream or member.voice.self_video):
      using_cam = True
    # Start studying
    if (not before.channel or before.channel.id in channels.NotForStudying) and after.channel and studycol.count_documents({"_id": member.id}) == 0 and not after.channel.id in channels.NotForStudying:
      if len(after.channel.members) >= 11: # 11 because this member is included into the count as well
        await NewPrestige(member.id, "studyarmy")
      init_relationships = {}
      for relation in studycol.find():
        init_relationships[str(relation.get("_id"))] = time.time()
      studycol.update_many({}, {"$set": {f"relationships.{member.id}": time.time()}})
      studycol.insert_one({
        "_id": member.id,
        "study_begin": time.time(),
        "cam_usage": 0,
        "relationships": init_relationships
      })
      asyncio.get_event_loop().create_task(PlayJoinStudySound(member.id, after.channel))
      if GetUserAttr(member.id, "buddy_tracking_consent") is None:
        asyncio.get_event_loop().create_task(ConfirmBuddyTrackingConsent(member))
      if after.channel.id == channels.VCCamOn and GetUserAttr(member.id, "cam_on_aware") != True:
        SetUserAttr(member.id, "cam_on_aware", True)
        embed = discord.Embed()
        embed.title = "Important context about this voice channel"
        embed.description = f"Hey, {member.name}!\nYou joined the Cam On study channel.\nThis study channel is special as you have to enable your camera to be here.\nIf you don't want to, you may use any another study channel instead.\nUnfortunately you will be kicked from the channel in 5 minutes if you don't enable your camera by then."
        embed.colour = 0xbc9a4f
        try:
          await member.send(embed=embed)
        except:
          await bot.get_channel(channels.BotCommands).send(member.mention, embed=embed)
    if studycol.count_documents({"_id": member.id}) > 0 and using_cam:
      studycol.update_one({"_id": member.id}, {"$set": {"cam_usage_begin": time.time()}})
    if not using_cam and studycol.count_documents({"_id": member.id, "cam_usage_begin": {"$exists": True}}) > 0:
      cam_usage_begin = studycol.find_one({"_id": member.id}).get("cam_usage_begin")
      studycol.update_one({"_id": member.id}, {
        "$unset": {"cam_usage_begin": ""},
        "$inc": {"cam_usage": time.time() - cam_usage_begin}
      })
    # Stop studying
    if before.channel and (not after.channel or after.channel.id in channels.NotForStudying) and studycol.count_documents({"_id": member.id}) > 0:
      await StopStudying(member.id)
    if not member.bot:
      for chan in [before.channel, after.channel]:
        if chan is None:
          continue
        if vcrolescol.count_documents({"channel": chan.id}) == 0:
          if len(chan.members) >= 2 and not chan in channels.NotForStudying:
            role = await bot.guilds[0].create_role(name=chan.name, colour=0x84b500, mentionable=True)
            vcrolescol.insert_one({
              "channel": chan.id,
              "role": role.id
            })
            for member in chan.members:
              if not member.bot:
                await member.add_roles(role)
        else:
          role = bot.guilds[0].get_role(vcrolescol.find_one({"channel": chan.id}).get("role"))
          if role is None:
            vcrolescol.delete_one({"channel": chan.id})
            continue
          if len(chan.members) < 2:
            await role.delete()
          else:
            for member in role.members:
              if not member in chan.members:
                # Member with role is not in the vc
                await member.remove_roles(role)
            for member in chan.members:
              if not role in member.roles:
                await member.add_roles(role)
    await CheckCamMembers()
    await UpdateStatus()


async def StopStudying(member_id, simulated=False, simulator=0):
    member = bot.guilds[0].get_member(member_id)
    if member is None:
      studycol.delete_one({"_id": member_id})
      return
    doc = studycol.find_one({"_id": member.id})
    studycol.delete_one({"_id": member.id})

    studytime_elapsed = time.time() - doc.get("study_begin")
    cam_usage = doc.get("cam_usage")
    used_cam = cam_usage > studytime_elapsed * 0.75

    studycol.update_many({}, {"$unset": {f"relationships.{member.id}": ""}})

    new_relations = 0

    session_relations = doc.get("relationships") or []
    if not GetUserAttr(member.id, "buddy_tracking_consent"):
      session_relations = []
    for relation in session_relations:
      relation_num = int(relation)
      if GetUserAttr(relation_num, "buddy_tracking_consent") and not relation_num in (GetUserAttr(member.id, "matched_relations") or []):
        if buddytrackingcol.count_documents({"buddies": {"$all": [member.id, relation_num]}}) == 0:
          buddytrackingcol.insert_one({
            "buddies": [member.id, relation_num],
            "tracking_expiration": time.time() + 60 * 60 * 24 * 14,
            "individual_study_time": {relation: 0, str(member.id): 0},
            "mutual_study_time": 0
          })
          new_relations += 1
      else:
        continue
      buddytrackingcol.update_one({
        "buddies": {"$all": [member.id, relation_num]}
      }, {
        "$inc": {"mutual_study_time": time.time() - session_relations[relation]}
      })

      # See if they match!
      doc_relation = buddytrackingcol.find_one({"buddies": {"$all": [member.id, relation_num]}})
      individual_study_time = doc_relation.get("individual_study_time")
      min_study_time = 60 * 60 * 12
      if individual_study_time[str(member.id)] > min_study_time and individual_study_time[relation] > min_study_time and doc_relation.get("mutual_study_time") / min(individual_study_time[str(member.id)], individual_study_time[relation]) > .8:
        buddytrackingcol.delete_one({"_id": doc_relation.get("_id")})
        buddy1 = await bot.fetch_user(member.id)
        buddy2 = await bot.fetch_user(relation_num)
        usercol.update_one({
          "_id": buddy1.id
        }, {
          "$push": {"matched_relations": buddy2.id}
        })
        usercol.update_one({
          "_id": buddy2.id
        }, {
          "$push": {"matched_relations": buddy1.id}
        })
        priv_chan = await bot.get_channel(channels.BuddyChatsCategory).create_text_channel(
          buddy1.name + "-" + buddy2.name,
          topic="You two have been matched by the buddy tracking machine, discuss!"
        )
        await priv_chan.set_permissions(buddy1, view_channel=True)
        await priv_chan.set_permissions(buddy2, view_channel=True)
        embed = discord.Embed()
        embed.title = "<:ciccio:937053048486920212> Buddy Match <:ciccio:937053048486920212>"
        embed.description = f"Hello, {buddy1.mention} and {buddy2.mention}!\nWe (the machine) have recognized that you two often study around the same time and could potentially be study buddies. You can discuss your compatibility in this private channel which will be __automatically deleted in 3 days__. The conversations can also continue in DMs if you both consent to it. All the best!"
        embed.set_footer(text="Click the 🗑️ to delete this channel now, if any of you happen to not be interested in this offer.")
        embed.colour = 0xb668c9
        imsg = await priv_chan.send(buddy1.mention + buddy2.mention, embed=embed)
        matchchanscol.insert_one({
          "buddies": [buddy1.id, buddy2.id],
          "channel": priv_chan.id,
          "message": imsg.id,
          "expiration": time.time() + 60 * 60 * 24 * 3
        })

        await imsg.add_reaction("🗑️")
        await imsg.pin()
        await priv_chan.send("Don't know what to say? Here are some things you can ask about to see if you would fit as buddies...\n- Time zone\n- Schedule hours\n- Study techniques\n- Field of study")
    buddytrackingcol.update_many({"buddies": {"$in": [member.id]}}, {"$inc": {f"individual_study_time.{member.id}": studytime_elapsed}})

    buddytrackingcol.delete_many({"tracking_expiration": {"$lt": time.time()}}) # Delete expired data

    maxtime = 6 * 60 * 60
    limitreached = False
    actual_studytime_elapsed = studytime_elapsed
    if studytime_elapsed > maxtime and not simulated:
      studytime_elapsed = maxtime
      limitreached = True
    # Check prestiges:
    if studytime_elapsed > 2 * 60 * 60:
      await NewPrestige(member.id, "twohourstudy")
    if datetime.datetime.today().weekday() == 6:
      #sunday
      await NewPrestige(member.id, "sundaystudy")
    # End check prestiges
    earnstudytokens = round(studytime_elapsed * (presets.SilentETokens if not used_cam else presets.CamETokens))
    earncoins = round(studytime_elapsed * (presets.SilentECoins if not used_cam else presets.CamECoins))
    before_rank = GetUserRank(member.id, default="unavailable")
    AddUserTokens(member.id, earnstudytokens)
    after_rank = GetUserRank(member.id, default="unavailable")
    AddUserCoins(member.id, earncoins)
    SetUserAttr(member.id, "studytime", (GetUserAttr(member.id, "studytime") or 0) + studytime_elapsed)
    earnxp = int(studytime_elapsed)
    await AddExperience(member, member.id, earnxp)

    weeklystatscol.update_one({
      "user": member.id,
      "week": int(time.time() / 60 / 60 / 24 / 7)
    }, {
      "$inc": {
        "studytime": studytime_elapsed
      }
    }, upsert=True)
  
    archive_id = random.randint(10**10, 10**11)
    sessionarchivecol.insert_one({
      "_id": archive_id,
      "archived": time.time(),
      "user": member.id,
      "studytime": studytime_elapsed,
      "coins": earncoins,
      "studytokens": earnstudytokens,
      "experience": earnxp,
      "weekly_affected": weeklystatscol.find_one({"user": member.id, "week": int(time.time() / 60 / 60 / 24 / 7)}).get("_id")
    })
    if sessionarchivecol.count_documents({}) >= 500:
      await bot.get_channel(channels.BotCommands).send("Performing an archive purge on all archives older than 2 days...")
      sessionarchivecol.delete_many({"archived": {"$lt": time.time() - 2 * 24 * 60 * 60}})
      await bot.get_channel(channels.BotCommands).send("Archive purge done.")
    smmode = GetUserAttr(member.id, "studymessages")
    if smmode is None:
      smmode = True
    hasgoal = (GetUserAttr(member.id, "dailygoal") or [0, 0, 0])[2] == math.floor(time.time() / 24 / 60 / 60)
    try:
      if not smmode is False:
        embed = discord.Embed()
        embed.description = f"<a:greatwork:961366842868367370> Studied for `{GetTimeString(studytime_elapsed)}`" + (f"\n\n<a:greatwork:961366842868367370> [`+{earnstudytokens:,d}`](https://. \"Earned study tokens\") study tokens <:book:816522587424817183>" if not NoTokens(member.id) else "") + f"\n\n<a:greatwork:961366842868367370> [`+{earncoins:,d}`](https://. \"Earned coins\") coins <:famcoin2:845382244554113064>" + ("\n\n<a:greatwork:961366842868367370> Camera/screenshare bonus!" if used_cam else "") + (f"\n\n<a:greatwork:961366842868367370> <:beaver_2:841722221671743488> Woo! You climbed the leaderboard: [`{before_rank}`](https://. \"Your previous rank\") **➝** [`{after_rank}`](https://. \"Your current rank\")" if before_rank != after_rank else (f"\n\n<a:greatwork:961366842868367370> Your leaderboard rank is [`{after_rank}`](https://. \"Your rank\")" if not NoTokens(member.id) else "")) + (f"\n\n<a:greatwork:961366842868367370> {new_relations} new relation(s) created (AARSBIMS)" if new_relations > 0 else "") + (f"\n\n<:WokePepe:728196813412106270> Oh no! You studied for `{GetTimeString(actual_studytime_elapsed)}` which exceeds the study session limit of 6 hours. Your earnings and study time was shortened to the limit instead of how long time you actually spent in there." if limitreached else "") + ("\n\n<a:greatwork:961366842868367370> You got closer to your study goal" if hasgoal else "")
        embed.colour = 0x36393f#0x67356b
        randomquote = random.choice([
          "I hope you will appreciate your return.",
          "I admire you!",
          f"I love you, {member.name}!",
          f"ILY {member.name}!!!!",
          "Even better now.",
          "With great success comes great success.",
          "Can you see me?",
          "Are you set?",
          "Great effeciency!",
          "Great work, as always!",
          "( ノ ^o^)ノ",
          "w(ﾟДﾟ)w ... wow... that session was amazing.",
          "Now, time for 🍰.",
          "I am speechless.",
          "Your company here? (ʘ ͜ʖ ʘ) Call 159.89.141.152.",
          "Congratulations!",
          "D_D"
        ])
        embed.set_author(name=randomquote)
        embed.description += f"\n\n[Disable or change location of session results?](https://discord.com/channels/712808127539707927/713177565849845849/796105551229616139 \"Click to see how you can prevent these messages from being sent to you\")" + (f"\n[SESSION WAS SIMULATED BY {simulator}]" if simulated else "")
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/802215570996330517/889594173861269605/momentum_session_complete.png")
        embed.set_footer(text=f"Archive ID: {archive_id}")
        if smmode is True:
          try:
            await member.send(embed=embed)
          except:
            await bot.get_channel(channels.BotCommands).send(f"Hello {member.mention}!\nI tried to send you this study sessions's results, but it couldn't be delivered.\nHave you disabled private messages from being sent to you? To enable, go to the server's privacy settings and enable \"Direct Messages\".\nIf you instead want to receive the results in the server, type \"mom studymessages server\" here.\nIf you don't want to receive the results anymore, type \"mom studymessages off\".")
        elif smmode == "server":
          await bot.get_channel(channels.BotCommands).send(member.mention, embed=embed)
        await bot.get_channel(channels.BotLogs).send("`" + str(member.id) + " - " + member.name + "`", embed=embed)
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
    embed.set_thumbnail(url=user.display_avatar.with_size(128).url)
    if not NoTokens(user.id):
      embed.add_field(name="<:book:816522587424817183> Study tokens", value=f"`{GetUserTokens(user.id):,d}`")
    embed.add_field(name=(("<:famcoin2:845382244554113064> Coins" if user.id != 824316055681761320 else "<a:cat_popcorn:853734055765606430> Popcorn bank") if user.id != 577934880634306560 else "<a:1150_pugdancel:856637771795267614> Doggy bank") if user.id != 799293092209491998 else "🐖 Piggy bank", value=f"**{GetUserCoins(user.id):,d}**")
    studytime = GetUserAttr(user.id, "studytime")
    embed.add_field(name="<:hourglass:816596944330817536> Study time", value=GetTimeString(studytime) if studytime is not None else "No study session yet!")
    if not NoTokens(user.id):
      embed.add_field(name="🧗 Rank", value="`" + str(GetUserRank(user.id, default="Unavailable")) + "`")
    prog = lvlinfo["progress"]
    req = lvlinfo["required"]
    rem = lvlinfo["remaining"]
    embed.add_field(name="<:4813bigbrain:861353869216841769> Experience", value=f"[{prog:,d}" + " / " + f"{req:,d}](https://. \"{rem:,d} left\")" + " (" + str(lvlinfo["progresspercent"]) + "%)")

    #embed.add_field(name="<:beaver_2:841722221671743488> Bump contributions", value=f'{GetUserAttr(user.id, "bump_count") or "No contributions yet!"}')

    if GetUserAttr(user.id, "donations") is not None:
      embed.add_field(name="<:pandalove:720968101532794910> Donated", value="Thank you for your donation.")
    
    cardcount = len(GetUserAttr(user.id, "card_inventory") or [])
    embed.add_field(name="<:crunchys:861351443004915712> Trade cards", value=cardcount if cardcount > 0 else "No trade cards yet!")

    embed.description = "**[`  " + (" " * 11) + str(lvlinfo["level"]) + (" " * (11 - len(str(lvlinfo["level"])))) + "  `](https://. \"Level\")**\n"
    BAR_ON = "<:_:816596886852599870>"
    BAR_OFF = "<:_:816596916896530432>"
    for i in range(10):
      mode = not (lvlinfo["progresspercent"] / 10) <= i
      embed.description += BAR_ON if mode else BAR_OFF
    embed.description += "\n\n[Confused by the different stats?](https://discord.com/channels/712808127539707927/713177565849845849/796415766005284874 \"Click here to see an explanation of them\")"
    if NoTokens(user.id):
      embed.description += f"\n[{sanitize(user.name)} has disabled study tokens.](https://discord.com/channels/712808127539707927/713177565849845849/807738082903457802 \"More information about disabling study tokens\")"
    if user.joined_at is not None:
      embed.description += "\n*Joined " + GetTimeString(time.time() - user.joined_at.timestamp()) + " ago*"
    if studycol.count_documents({"_id": user.id}) != 0:
      embed.description += f"\n\n> {user.name} is studying ({GetTimeString(time.time() - studycol.find_one({'_id': user.id}).get('study_begin'))})"


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
    try:
      embed.set_thumbnail(url=n1mem.display_avatar.with_size(64).url)
    except:
      pass
    embed.description = ""
    ii = (page - 1) * 10
    i = ii
    for user in lbdoc:
      i += 1
      mem = bot.guilds[0].get_member(user.get("_id"))
      name = sanitize(mem.name if mem else "<User left server>")
      st = user.get("studytokens")
      embed.description += "[`#" + str(i) + ("🥇" if i == 1 else "") + "`](https://. \"Rank\") **" + name + "**" + (" [**  ⟵ YOU**](https://. \"This is you\")" if user.get("_id") == ctx.author.id else "") + "\n⤷  " + f"{st:,d}" + "\n"
    if i == ii:
      embed.description = "Empty page."
    selfrank = GetUserRank(ctx.author.id)
    embed.description += f'\nYour leaderboard rank is [`{selfrank or "unavailable"}`](https://. "{sanitize(ctx.author.name)}\'s rank")'
    if selfrank is None:
      embed.description += "\n[Why am I not shown on the leaderboard?](https://discord.com/channels/712808127539707927/713177565849845849/831853167858942012 \"Click to see why you are not shown on the leaderboard\")"
    embed.colour = 0x2f3136
    embed.set_footer(text=f"Page {page}/{pagecount}")
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx, *, showcategory=None):
    embed = discord.Embed()
    if showcategory is None:
      embed.description = f"Hey!\n**Momentum** is the bot for Study Fam. I will keep track of your studying, and at the same time serve much more features to keep your stay here as great as possible.\nAll you have to do is join a voice channel and get studying!\nThese are just some of the things I serve:\n• Tracking your studying\n• Leaderboard\n• Tools, preferences and options\n**Questions? Suggestions?** [Feel free to ask us](https://discord.com/channels/712808127539707927/857739970978775040/858281583348547584 \"Click to ask a question or suggest something\") or [see common questions and answers](https://discord.com/channels/712808127539707927/713177565849845849/845653574990168065 \"Click to see a list of common questions and their answers\").\n\nType `mom help <category>` to see the commands of a category."
      for categ in helpmenu:
        embed.description += f'\n\n☞ [**{categ["name"]}**](https://. \'Type "mom help {categ["name"]}" to see the commands of this category\')\n{categ.get("description") or "No description."}\n*{len(categ["commands"])} commands*'
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
          embed.description += f'\n\n❯ [`{cmdname}`](https://. "{fullcmdusage}"){"||`" + cmdusage + "`||" if len(command[0]) > 0 else ""} {command[1]}'
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
    randomPun = random.choice([
      "These puns are paid for by your monthly taxes.",
      "So my mate was at a fancy dress party dressed as a bank vault.\nI said: ''I thought you were coming dressed as an apology?''\nHe said: 'Well, I thought I'd better be safe than sorry''.",
  "England doesn’t have a kidney bank.\nBut it does have a Liverpool.",
      "I got fired from my job at the bank today. An old lady asked me to check her balance...\n...so I pushed her over.",
      "Why couldn't the skeleton rob the bank?\nIt didn't have the guts.",
  "I invested in a bank that gave 0% interest.\nIt made no cents.",
      "Why did the football player go to the bank?\nTo get his Quarter Back!",
      "So this bank robber I know brings a bathroom scale with him to every heist.\nHe always gets a weigh.",
  "What did the tree do when the bank was closed?\nStarted its own branch.",
      "If you have no interest in banking...\nyou are not a loan.",
      "Why did the bank owner buy cows?\nTo beef up security."
    ])
    embed.description = f"{ctx.author.mention} gave [`{amount:,d}`](https://. \"Coins given\") coins to {user.mention}.\n\n{user.mention} now has `{GetUserCoins(user.id):,d}` coins!\n\nTHANK YOU FOR TRANSFERING MONEY WITH ME, HERE'S YOUR REWARD:\n> " + randomPun
    embed.colour = 0x45725b
    embed.set_thumbnail(url="https://icons.iconarchive.com/icons/aha-soft/business-toolbar/48/payment-icon.png")
    await ctx.send(ctx.author.mention, embed=embed)


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
    if ((usercol.find_one({"_id": ctx.author.id}).get("flipwinnings") or {}).get(str(todayint)) or 0) >= 1000:
      await ctx.send("<:kermittest:815565956281401354> You've won too much money by doing this today. Come back another day to flip a coin.")
      return
    if amount > 200:
      await ctx.send("You cannot bet for more than 200 coins.")
      return
    if amount < 30:
      await ctx.send("You must bet at least 30 coins.")
      return
    if amount > GetUserCoins(ctx.author.id):
      await ctx.send("You don't have that much money!")
      return
    if random.randrange(0, 151) == 150:
      await AddExperience(ctx, ctx.author.id, 5000)
      AddUserCoins(ctx.author.id, 5000)
      await ctx.send(embed=discord.Embed(
        title="<:SanjiPepeLaugh:739592274253578260><:SanjiPepeLaugh:739592274253578260> INSANE LUCK!! <:SanjiPepeLaugh:739592274253578260><:SanjiPepeLaugh:739592274253578260>",
        description="Wowowowow!\n**The coin landed on its vertical side!**\n`+5,000` coins!",
        colour=discord.Colour.orange()
      ))
      return
    choice = sides.index(choice.lower())
    coinside = random.randrange(0, 2)
    won = coinside == choice
    embed = discord.Embed()
    embed.title = ("🤑" if won else "💀") + " " + sides[coinside].upper()
    embed.description = f"{ctx.author.mention} bet `{amount:,d}` coins on `{sides[choice]}` and **" + ("WON" if won else "LOST") + "**!\n`" + (("+" + str(int(amount * 1.5))) if won else ("-" + str(amount))) + " coins`"
    embed.colour = discord.Colour.green() if won else discord.Colour.red()
    await ctx.send(embed=embed)
    getcoins = int(amount * 1.5) if won else -amount
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
      embed.description += f"\n☞ [`{itemname}`](https://. \"Role name\") <:famcoin2:845382244554113064> `{item[0]:,d}`" + (f" • **Lasts {GetTimeString(item[3])}**" if len(item) >= 4 else "") + (f" (**[OWNED](https://. \"You own this role, and you cannot buy it\")**)" if discord.utils.get(ctx.author.roles, id=item[2]) else "") + f"\n{item[1]}\n"
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
    itemrole = discord.utils.get(bot.guilds[0].roles, id=item[2])
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
    #brole = discord.utils.get(bot.guilds[0].roles, id=item[2])
    # this is a duplicate of itemrole??
    await ctx.send(ctx.author.mention, embed=discord.Embed(
      title=f"<:famcoin2:845382244554113064> Purchased {itemname}",
      description=f"You purchased the role {itemrole.mention} for `{item[0]:,d}` coins.\n> {item[1]}" + (f"\nYou will lose this role in `{GetTimeString(item[3])}`" if len(item) >= 4 else ""),
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
      embed.description += f'\n☞ [`{packname}`](https://. "Pack name") <:famcoin2:845382244554113064> `{pack["cost"]:,d}` ({len(pack["cards"])} possible cards)' + (f' - **{round((len(cardsownedc) / len(pack["cards"])) * 100)} % collected**' if len(cardsownedc) > 0 else "") + f'\n{pack["description"]}\n'
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
          embed.description = f'<:shibacheer:720961100375523369> The pack contained:\n{tradecards.rarity_emojis[cardobj["rarity"]]} [`{tradecards.rarities[cardobj["rarity"]]}` **{cardobj["name"]}**](https://. "You received this card")\n\n*{sanitize(cardobj["quote"])}*' + (f"\n\nDuplicate card! **{dupecount}x**" if duplicate else "")
          embed.set_image(url="attachment://tradecard.png")
          embed.colour = tradecards.rarity_colours[cardobj["rarity"]]
          await ctx.send(ctx.author.mention, file=file, embed=embed)
          chosencard = True
          break

@bot.command(aliases=["tradecards", "mytradecards", "cardlist", "cards", "cardinventory", "cardinv", "inventory", "inv"])
async def mycards(ctx):
    cards = GetUserAttr(ctx.author.id, "card_inventory") or []
    fixed = []
    for cardidx in cards:
      card = tradecards.tradecards[cardidx]
      if card in fixed:
        continue
      fixed.append(card)
    fixed = sorted(fixed, key=lambda d: d["rarity"], reverse=True)
    embed = discord.Embed()
    embed.title = "Study Fam Card Collection"
    embed.description = f'This is your card collection.\n`{len(fixed)}/{len(tradecards.tradecards)}` unique cards (`{len(cards)}` in total).\nUse `mom cardinfo <card>` to see information about a card.\n'
    for card in fixed:
      count = cards.count(tradecards.tradecards.index(card))
      embed.description += f'\n\n[`{card["name"]}`](https://. "Card name") {"**{0}x** ".format(count) if count != 1 else ""}{tradecards.rarity_emojis[card["rarity"]]}'
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
    embed.description = (f'*{sanitize(card["quote"])}*\n\nRarity: {tradecards.rarity_emojis[card["rarity"]]} `{tradecards.rarities[card["rarity"]]}`\nMade by: {author.mention if author else "Unknown"}\nYou own: [`{owncount}x`](https://. \"You have this many of this card\")\n' if owncount > 0 else "") + f'{totalowners} people have this card'
    if owncount > 0:
      embed.colour = tradecards.rarity_colours[card["rarity"]]
      embed.set_image(url="attachment://tradecard.png")
      async with ctx.typing():
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
    if totaltime > 20 * 60 * 60:
      await ctx.send("<a:download1:745404052598423635> What are you doing??\nDon't put your goal that high, max 20 hours.")
      return
    if (time.time() + totaltime + (30 * 60)) > int((time.time() / (24 * 60 * 60)) + 1) * 24 * 60 * 60:
      await ctx.send("<a:download1:745404052598423635> Oops! I'm sorry, but if you would start studying now until you reach the goal, you would finish later than 23:30 in UTC+0 which is 30 minutes before goal reset. Therefore you cannot set that goal at the moment.")
      return
    if totaltime >= 4 * 60 * 60:
      await NewPrestige(ctx.author.id, "planner")
    SetUserAttr(ctx.author.id, "dailygoal", [totaltime, totaltime, math.floor(time.time() / 24 / 60 / 60)])
    await AddExperience(ctx, ctx.author.id, 200)
    await ctx.send(ctx.author.mention, embed=discord.Embed(
      description=f"<:wow:762241502898290698> Your goal of `{GetTimeString(totaltime)}` has been made, start studying and try[*](https://discord.com/channels/712808127539707927/713177565849845849/822971544098963456 \"Click for motivation\") reach it!\nSee your progress with the command `mom mygoal`.",
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
    progress = (ttot - tleft) / ttot
    embed = discord.Embed()
    embed.title = f"Study Goal: `{int((ttot - tleft) / ttot * 100)}%`"
    embed.description = f"{GetTimeString(ttot - tleft)} finished out of {GetTimeString(ttot)}\n({GetTimeString(tleft)} remaining)"
    embed.set_footer(text="Note that this is not updated until you exit your study session!")
    start_color = (47, 49, 54)
    end_color = (0, 255, 0)
    rgb = (
      math.floor(start_color[0] + progress * (end_color[0] - start_color[0])),
      math.floor(start_color[1] + progress * (end_color[1] - start_color[1])),
      math.floor(start_color[2] + progress * (end_color[2] - start_color[2]))
    )
    embed.colour = int("%02x%02x%02x" % rgb, 16)
    await ctx.send(embed=embed)



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
    embed.description = f"Fellow officers, here is a bounty.\nClaim it with `mom claimbounty {refid}`!\n\nCreated by: {provider.mention}\nChallenge: `{description}`\nPrize: <:famcoin2:845382244554113064> `{deposit:,d}`\nClaim status: [{statusicon} **{statusmode}**](https://. \"Whether this bounty is claimable or not\")" + (" (<@" + str(doc.get("claimed_by")) + ">)" if doc.get("claimed") else "")
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
    AddUserCoins(ctx.author.id, doc.get("input"))
    bntcol.delete_one({"provider": ctx.author.id})
    await ctx.send(ctx.author.mention + "\nYour bounty has been canceled!\nYou got your bounty input of `" + str(doc.get("input")) + "` coins back.")



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
      if totaltime > 30 * 24 * 60 * 60:
        await ctx.send("Max 30 days for timer. The timer has not been set.")
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
    frame = Image.open("images/frames/new_card_frame_" + ["common", "uncommon", "rare", "legendary", "god"][obj["rarity"]] + ".png").convert("RGBA")
    tradecard = Image.open(tradecards.folderpath + obj["image"]).convert("RGBA")
    framedcard = Image.new("RGBA", frame.size)
    #height for old frames: 25px. For new: 56px
    framedcard.paste(tradecard, (34, 56), tradecard)
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
      avatar = Image.open(requests.get(author.display_avatar.with_size(32).url, stream=True).raw).convert("RGBA")
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
      #277708587554308096, #anivya
      645256353966981120, #amelia
    ]
    imgs = []
    frames = 30
    for a in ctna:
      o = Image.open(requests.get((bot.guilds[0].get_member(a)).display_avatar.with_size(128).url, stream=True).raw)
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
          embed.description = f'<:shibacheer:720961100375523369> You merged `{requiredcards}` `{tradecards.rarities[mergerarity]}` cards into one:\n{tradecards.rarity_emojis[cardobj["rarity"]]} [`{tradecards.rarities[cardobj["rarity"]]}` **{cardobj["name"]}**](https://. "You received this card")\n\n*{sanitize(cardobj["quote"])}*' + (f"\n\nDuplicate card! **{dupecount}x**" if duplicate else "")
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
            embed.description += f'[`{tradecards.tradecards[card]["name"]}`](https://. "Type a card\'s name to merge it") (**{fixed[card]}x**) '
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
              deck += f'\n**{trader["cards"][card]}x** [{tradecards.tradecards[card]["name"]}](https://. "Card name")'
            deck += f'\n**[{"✓ Ready" if trader["status"] == 1 else "🞬 Not ready"}](https://. "Status")**'
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
        embed.description += f"\n{role[0].mention}: Expires in **[{GetTimeString(role[1] - time.time())}](https://. \"Temporary role expires\")**"
    embed.colour = 0xf47c3f
    embed.set_thumbnail(url="https://i.imgur.com/zHwbaVS.png")
    await ctx.send(embed=embed)




@bot.command()
@debugging_only()
async def error(ctx):
    raise Exception




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
    if action in ["start", "begin", "continue", "s", "c"]:
      if settings["begin"] is None and settings["pause"] is None:
        settings["begin"] = time.time()
        await ctx.send("Started stopwatch!")
      elif settings["pause"] is not None:
        settings["remove"] += time.time() - settings["pause"]
        settings["pause"] = None
        await ctx.send("Continued stopwatch.")
      else:
        await ctx.send("You cannot start the stopwatch right now because it's already running. The timer must either be paused or not active to be started.")
    elif action in ["stop", "end", "e"]:
      if settings["begin"] is not None:
        if settings["pause"] is not None:
          settings["remove"] += time.time() - settings["pause"]
          settings["pause"] = None
        await ctx.send(embed=discord.Embed(
          title="Stopwatch has ended",
          description=f'You stopped your stopwatch.\nStopwatch took [**`{GetTimeString(time.time() - settings["begin"] - settings["remove"])}`**](https://. "Stopwatch took this long").',
          colour=0x96213a
        ))
        settings["begin"] = None
      else:
        await ctx.send("Your stopwatch is not active, therefore you cannot stop it.")
    elif action in ["pause", "p"]:
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
          description=("**Stopwatch is paused**\n" if settings["pause"] is not None else f'Stopwatch has taken [**`{GetTimeString(time.time() - settings["begin"] - settings["remove"])}`**](https://. "Stopwatch has taken this long so far").\n') + f'Stopwatch was started `{GetTimeString(time.time() - settings["begin"])}` ago.\n\nUse `mom stopwatch stop` to end the stopwatch or `mom stopwatch pause`/`mom stopwatch continue` to pause it or continue it.',
          colour=0x29213f
        ))
    else:
      await ctx.reply("That's not a valid action!")


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

@bot.command(aliases=["message", "anonymous", "a"])
async def anon(ctx, *, message=None):
  if not ctx.channel.id in channels.AllowAnonymousMessages:
    await ctx.message.delete()
    await ctx.send(ctx.author.mention + " Sorry, but you can't make anonymous messages here, to prevent abuse. Please retry in an *emotional* channel.", delete_after=10)
    return
  if message is None:
    await ctx.send("No message was provided!")
    return
  def generatecode(iter=0):
    if iter >= 1000:
      return 0
    tcode = random.randint(10**4, 10**5)
    return tcode if anoncol.count_documents({"code": tcode}) == 0 else generatecode(iter + 1)
  code = generatecode()
  if code == 0:
    await ctx.send("Sorry, could not generate a valid code.")
    return
  await ctx.message.delete()
  embed = discord.Embed()
  embed.set_author(name="Anonymous #" + str(code), icon_url="https://icons.iconarchive.com/icons/flameia/xrabbit/128/Tools-Terminal-icon.png")#"https://icons.iconarchive.com/icons/pixelmixer/basic-2/32/user-anonymous-icon.png")
  embed.description = message
  embed.colour = 0x2f3136
  replyto = ctx.message.reference
  if replyto is None:
    try:
      msg = await ctx.send(embed=embed)
    except:
      pass
  else:
    msgreply = await ctx.fetch_message(replyto.message_id)
    msg = await msgreply.reply(embed=embed)
  anoncol.insert_one({
    "_id": msg.id,
    "code": code,
    "author": ctx.author.id,
    "message": message
  })
  await ctx.author.send("Hello there!\nHere's just some information about anonymous messages within Momentum.\nYou just posted an anonymous message.\nUsers cannot see who posted what you did.\n**If you notice that the message you sent still remains in the chat and not get deleted, don't worry! That is a common client bug that can be fixed by refreshing Discord.**\nTo delete your anonymous message, click the message's reply button and type \"mom delanon\".\n\nPrivacy notice: anonymous messages' authors are saved in a secure database to prevent spam and abuse.")

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
@admin_only()
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
    for studying in studycol.find():
      member = bot.guilds[0].get_member(studying.get("_id"))
      if member:
        desc += "\n" + member.mention + " - **" + GetTimeString(time.time() - studying.get("study_begin")) + "**" + (" \📸" if studying.get("cam_usage_begin") is not None else "")
    embed.description = desc
    embed.colour = 0x3f528c
    try:
      embed.set_thumbnail(url=bot.guilds[0].get_member(studycol.find_one({}).get("_id")).display_avatar.with_size(64).url)
    except:
      pass
    await ctx.send(embed=embed)

@bot.command()
async def type(ctx):
    await ctx.message.delete()
    async with ctx.typing():
      await asyncio.sleep(10)

@bot.command()
@admin_only()
async def simstudy(ctx, user: discord.Member=None, *, studytime=None):
    if user is None:
      await ctx.send("Didn't provide member to simulate the studying on.")
      return
    saved_doc = None
    if studycol.count_documents({"_id": user.id}) > 0:
      saved_doc = studycol.find_one({"_id": user.id})
      studycol.delete_one({"_id": user.id})
    if studytime is None:
      await ctx.send("Didn't provide a time amount.")
      return
    thetime = StringToTime(studytime)
    if thetime is None or thetime > 6 * 24 * 60 * 60 or thetime < 0:
      await ctx.send("Invalid study amount!")
      return
    msg = await ctx.send("Include camera/screenshare bonus? Type y/n.")
    used_cam = False

    def check(m):
      return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    try:
      m = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
      await msg.delete()
      await ctx.send("You didn't respond in time!")
    else:
      await m.delete()
      await msg.delete()
      content = m.content
      if content.lower() == "y":
        used_cam = True

    studycol.insert_one({
      "_id": user.id,
      "study_begin": time.time() - thetime,
      "cam_usage": thetime if used_cam else 0
    })
    await StopStudying(user.id, simulated=True, simulator=ctx.author.id)
    if saved_doc is not None:
      studycol.insert_one(saved_doc)
    await ctx.send("Successfully simulated study time to member!\n*" + ("No bonus was given" if not used_cam else "With bonus") + "*")


@bot.command()
async def brb(ctx):
    pointermessage = GetUserAttr(ctx.author.id, "brb_pointer_message")
    if pointermessage is None:
      pointermessage = await ctx.send("Great! Use `mom brb` again to get here.")
      SetUserAttr(ctx.author.id, "brb_pointer_message", pointermessage.jump_url)
    else:
      await ctx.reply("Hey, welcome back! Click here to get back to where you were: " + pointermessage)
      RemUserAttr(ctx.author.id, "brb_pointer_message")

@bot.command()
@admin_only()
async def verify(ctx, member: discord.Member=None):
  if member is None:
    await ctx.reply("You need to provide a member to verify.")
    return
  #await ctx.message.delete()
  await member.add_roles(discord.utils.get(bot.guilds[0].roles, id=713466849148534814), discord.utils.get(bot.guilds[0].roles, id=783777725487382570))
  embed = discord.Embed()
  embed.description = f"You have been verified and can now access the server!\nMake sure to **read the** <#857730667542741012> beforehand.\n\n3 Features Not To Miss On The Server:\n1️⃣ To find a study buddy, visit <#934841449315459183> for our automated system!\n2️⃣ For full focus, use the **distraction-free mode** of the server by running the command `mom nd` in <#713177565849845849>. Run the command again to return to full-access.\n3️⃣ Assign yourself the 🔔 newsfeed role (among many others) at <#847915130968211497>, so you don't miss out on our announcements!\n\nEnjoy your stay and good luck! <:shibacheer:720961100375523369>"
  embed.colour = 0xcaa7a7
  embed.set_footer(text="When you have read this, please send a confirmation so that we can wrap this up!")
  await ctx.send(member.mention, embed=embed)

  # Ghost pings in important channels:

  #for important_chan in channels.Important:
  #  await bot.get_channel(important_chan).send(member.mention, delete_after=0)



@bot.command()
async def joinstudybuddies(ctx):
    if studybuddiescol.count_documents({"_id": ctx.author.id}) > 0:
      await ctx.send("You're already signed up as a study buddy! If you want to edit your registration details, please unregister first with the `leavestudybuddies` command.")
      return
    preferences = []
    i = 0
    for selector in presets.StudyBuddyOptions:
      i += 1
      embed = discord.Embed()
      embed.set_author(name=f"Study Buddy Registration: {i}/{len(presets.StudyBuddyOptions)}")
      embed.title = selector["title"]
      embed.description = selector["description"] + "\n"
      j = 0
      for option in selector["options"]:
        j += 1
        embed.description += f"\n**{j}.** {option}"
      embed.colour = 0xb53f64
      choose_from = await ctx.send(embed=embed)
      def check(m):
        return m.author == ctx.author
      try:
        message = await bot.wait_for("message", timeout=60 * 5, check=check)
      except asyncio.TimeoutError:
        await choose_from.delete()
        await ctx.send("You did not answer in time, please retry.")
        break
      else:
        if not message.content.isnumeric():
          await choose_from.delete()
          await ctx.send("You should've responded with a number! Registration was canceled, please retry.")
          return
        chosen_option = int(message.content)
        if len(selector["options"]) >= chosen_option:
          await choose_from.delete()
          await message.delete()
          preferences.append(chosen_option - 1)
        else:
          await choose_from.delete()
          await ctx.send("Invalid number! Please retry!")
    studybuddiescol.insert_one({
      "_id": ctx.author.id,
      "preferences": preferences,
      "registered_at": time.time()
    })
    await ctx.send(embed=discord.Embed(
      title="You're signed up!",
      description="Thank you for signing up as a study buddy!\nWe will notify you in the study buddies channel when we find a match for you.\nTo see the status, type `mom studybuddies`.",
      colour=0x62935d
    ))
    await MatchStudyBuddies()


@bot.command()
async def leavestudybuddies(ctx):
    if studybuddiescol.count_documents({"_id": ctx.author.id}) == 0:
      await ctx.send("You have not signed up for study buddies yet.")
      return
    studybuddiescol.delete_one({"_id": ctx.author.id})
    await ctx.send(embed=discord.Embed(
      title="Resigned",
      description="You have resigned from the study buddies program.",
      colour=0x62935d
    ))

@bot.command()
async def studybuddies(ctx):
    embed = discord.Embed()
    embed.title = "Study Buddies Information"
    embed.description = "The study buddy program is a system built into me (Momentum) that automates finding study buddies that are similar to you. People who have been in the queue for a longer time are prioritized."
    own_doc = studybuddiescol.find_one({"_id": ctx.author.id})
    if own_doc is not None:
      value = "Type `mom leavestudybuddies` to resign."
      i = 0
      for selector in presets.StudyBuddyOptions:
        value += f"\n`{selector['title']}: " + selector["options"][own_doc.get("preferences")[i]] + "`"
        i += 1
      embed.add_field(name="You're signed up!", value=value)
    else:
      embed.add_field(name="Get started!", value="Type `mom joinstudybuddies` to join the program.")
    embed.add_field(name="Queue", value=f"There are currently `{studybuddiescol.count_documents({})}` waiting to find a study buddy!")
    embed.colour = 0x897939
    await ctx.send(embed=embed)


async def MatchStudyBuddies():
    for registered in studybuddiescol.find():
      perfect_match = studybuddiescol.find_one({
        "preferences": registered.get("preferences"),
        "_id": {"$not": {"$eq": registered.get("_id")}}
      }, sort=[("registered_at", 1)])
      if perfect_match is not None:
        buddy1 = await bot.fetch_user(registered.get("_id"))
        buddy2 = await bot.fetch_user(perfect_match.get("_id"))
        studybuddiescol.delete_many({"$or": [{"_id": buddy1.id}, {"_id": buddy2.id}]})
        embed = discord.Embed()
        embed.title = "<a:CS_Wiggle:856616923915878411> Study Buddy Match <a:CS_Wiggle:856616923915878411>"
        embed.description = f"Hello, {buddy1.mention} and {buddy2.mention}!\nYou two have been matched together. Please get in contact with each other!\nBoth of you have been removed from the program queue."
        embed.colour = 0x895139
        await bot.get_channel(channels.BuddyApplications).send(buddy1.mention + buddy2.mention, embed=embed)

async def ConfirmBuddyTrackingConsent(member: discord.Member):
    confirm_msg = await bot.get_channel(channels.BotCommands).send(member.mention, embed=discord.Embed(
      title="Enable Buddy Tracking?",
      description=f"Hello, {member.name}!\nDo you want me to track your study data to eventually suggest you a study buddy based on when you study?\nYou can change this at any time with `mom buddytracking`. Read more at <#934841449315459183>.\n\nType `yes` to consent to this, otherwise `no`. Please answer now, I will remind you about this offer until you respond.",
      colour=0xedeccb
    ))

    def check(m):
      return m.author.id == member.id and m.channel == confirm_msg.channel
    try:
      m = await bot.wait_for("message", timeout=5 * 60, check=check)
    except asyncio.TimeoutError:
      await confirm_msg.delete()
      #await confirm_msg.edit(content=member.mention + " **You did not respond in time! Please use the command instead if you want to enable buddy tracking.**")
    else:
      if m.content.lower() == "yes":
        SetUserAttr(member.id, "buddy_tracking_consent", True)
        await confirm_msg.delete()
        response = await m.reply("Thanks! Disable this at anytime with `mom buddytracking`.")
        await asyncio.sleep(10)
        await m.delete()
        await response.delete()
      else:
        SetUserAttr(member.id, "buddy_tracking_consent", False)
        await confirm_msg.delete()
        response = await m.reply("Okay, then! You can enable it whenever with `mom buddytracking`.")
        await asyncio.sleep(10)
        await m.delete()
        await response.delete()

@bot.command()
async def buddytracking(ctx):
    if not GetUserAttr(ctx.author.id, "buddy_tracking_consent"):
      SetUserAttr(ctx.author.id, "buddy_tracking_consent", True)
      await ctx.reply("Buddy tracking has been enabled!")
    else:
      cmsg = await ctx.reply(f'Are you sure that you want to disable buddy tracking and delete all saved data to it?\nYou have {buddytrackingcol.count_documents({"buddies": {"$in": [ctx.author.id]}})} generated relationships that will be deleted.\nType yes/no to confirm/deny.')
      def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
      try:
        m = await bot.wait_for("message", timeout=60, check=check)
      except:
        await cmsg.delete()
        await ctx.send("Timed out.")
      else:
        c = m.content.lower()
        await cmsg.delete()
        await m.delete()
        if c == "yes":
          buddytrackingcol.delete_many({"buddies": {"$in": [ctx.author.id]}})
          SetUserAttr(ctx.author.id, "buddy_tracking_consent", False)
          await ctx.reply("Buddy tracking has been disabled and your tracked data has been deleted.")
        else:
          await ctx.reply("Buddy tracking remains enabled. Your data has __not__ been deleted.")


temp_output_msg = None
callback_count = 0
exceeded_size = None

@bot.command()
async def revertsession(ctx, aid=None, *, studytime=None):
    if aid is None:
      await ctx.reply("You must provide the archive ID to revert the session. Please try again! The archive ID can be found at the bottom of the session result message.")
      return
    try:
      aid = int(aid)
    except:
      await ctx.reply(f"Archive ID `{aid}` is not a number (it has to be).")
      return
    doc = sessionarchivecol.find_one({"_id": aid})
    if doc is None:
      await ctx.reply("No archive was found with such ID! Make sure that you copied the code from the bottom of the session result message. If you did, the archive was probably deleted. Archives older than 2 days are purged when the total archive count reaches 500.")
      return
    member = bot.guilds[0].get_member(doc.get("user"))
    if not ctx.author.id in whitelist.admins and member.id != ctx.author.id:
        await ctx.reply("You must be either an admin or the owner of this session to revert it.")
        return
    await ctx.reply(f"Session belongs to {member.name}.\nReverting the session earnings and deleting archive...\nContained data: ||`{doc}`||")
    if studytime is not None:
        time_to_remove = StringToTime(studytime)
        total_time = doc.get("studytime")
        if time_to_remove > total_time:
            await ctx.reply("Cannot revert more time than the session contained.")
            return
        await ctx.reply(f"Reverting only `{GetTimeString(time_to_remove)}` of `{GetTimeString(total_time)}`.")
        await simstudy(ctx, user=member, studytime=GetTimeString(total_time - time_to_remove))
    SetUserAttr(member.id, "studytime", GetUserAttr(member.id, "studytime") - doc.get("studytime"))
    TakeUserCoins(member.id, doc.get("coins"))
    AddUserTokens(member.id, -doc.get("studytokens"))
    await AddExperience(member, member.id, -doc.get("experience"))
    sessionarchivecol.delete_one({"_id": aid})
    weeklystatscol.update_one({
      "_id": doc.get("weekly_affected")
    }, {
      "$inc": {
        "studytime": -doc.get("studytime")
      }
    })
    await ctx.send("Revert successful. Earnings were removed.")

@bot.command(aliases=["week"])
async def weekly(ctx):
    this_week_doc = weeklystatscol.find_one({"user": ctx.author.id, "week": int(time.time() / 60 / 60 / 24 / 7)}) or {"studytime": 0}
    old_weeks_docs = weeklystatscol.find({"user": ctx.author.id}, sort=[("week", -1)], skip=1, limit=3)
    week_leader_doc = weeklystatscol.find_one({"week": int(time.time() / 60 / 60 / 24 / 7)}, sort=[("studytime", -1)])
    older_weeks_str = ""
    for old_week in old_weeks_docs:
      older_weeks_str += " - " + GetTimeString(old_week.get("studytime"))
    weekly_leader = bot.guilds[0].get_member(week_leader_doc.get("user")) if week_leader_doc else None
    await ctx.send(embed=discord.Embed(
      title="Weekly study data",
      description=f"This week - **{GetTimeString(this_week_doc.get('studytime'))}**\nLast recorded weeks**{older_weeks_str}**\nThis week's leader - {weekly_leader.mention if week_leader_doc else 'no calculated leader'} (**{GetTimeString(week_leader_doc.get('studytime')) if week_leader_doc else 'none'}**)",
      colour=0x9ca830
    ))

@bot.command()
@admin_only()
async def reset_leaderboard(ctx, *, confirm=None):
  required_confirm_value = str(datetime.datetime.now().strftime("%-d %-m %Y"))
  if confirm == required_confirm_value:
    await CheckMonthlyLeaderboardReset(force=True)
    await ctx.reply("Reset the leaderboard!")
  else:
    await ctx.reply("Please rerun the command and append the **current day of the month, month, and year**, all separated by spaces in that order to confirm the leaderboard reset.")
