helpmenu = [
  {
    "name": "General",
    "description": "Momentum and Study Fam meta commands.",
    "aliases": ["basic", "meta", "default"],
    "commands": {
      "help": [[[False, "category"]], "Displays the help menu"],
      "credits": [[], "See the creators and contributors for Momentum"],
      "invite": [[], "Get an invite link that you can give to someone and when they use it you will earn coins"]
    }
  },
  {
    "name": "Studying & Tools",
    "description": "Preferences, tools, etc. These are commands to make your studying more efficient.",
    "aliases": ["study", "studying", "tools"],
    "commands": {
      "studymessages": [[[False, "mode"]], "Set how study results should be sent to you"],
      "setgoal": [[[True, "time"]], "Make a study goal for today"],
      "mygoal": [[], "View how your goal is going"],
      "toggletokens": [[], "Toggle study tokens (exclude/include yourself from leaderboard and monthly rankings)"],
      "reminder": [[], "Create a reminder/timer"],
      "myreminders": [[], "List your reminders"],
      "clearreminder": [[[True, "index"]], "Delete a reminder"],
      "stopwatch": [[[True, "start|stop|info"]], "Manage your stopwatch"],
      "makebounty": [[[True, "coins"], [True, "challenge"]], "Create a bounty challenge"],
      "cancelbounty": [[], "Cancel your unclaimed bounty challenge"],
      "claimbounty": [[[True, "id"]], "Claim a bounty"],
      "finishbounty": [[], "Complete your claimed bounty"],
      "togglenodistract": [[], "Toggle no-distraction mode"],
      "roles": [[], "View your temporary roles and see when they expire"],
      "anon": [[[True, "message"]], "Send a message anonymously"],
"delanon": [[], "Delete an anonymous message"],
      "studylist": [[], "Show a list of who is studying and for how long"],
      "togglesound": [[], "Toggle the sound effect that is played when you start studying"],
      "brb": [[], "Bring yourself back into the state of a conversation after you left"],
      # "joinstudybuddies": [[], "Register yourself for the automated study buddy program"],
      # "leavestudybuddies": [[], "Resign from the study buddy program"],
      # "studybuddies": [[], "Information about the study buddy program"],
      "buddytracking": [[], "Toggle if you want to be suggested possible study buddies"]
    }
  },
  {
    "name": "Competing & Data",
    "description": "About user's data, the leaderboard and competetive stats.",
    "aliases": ["competing", "data"],
    "commands": {
      "stats": [[[False, "user"]], "Shows information about a user"],
      "leaderboard": [[[False, "page"]], "Shows the study token leaderboard"],
      "prestiges": [[], "Shows your prestiges"]
    }
  },
  {
    "name": "Coins & Games",
    "description": "Manage your coins and buy things.",
    "aliases": ["coins", "games"],
    "commands": {
      "roleshop": [[], "Displays the role shop"],
      "buyrole": [[[True, "item"]], "Buy a role from the shop"],
      "pay": [[[True, "user"], [True, "amount"]], "Donate coins to someone"],
      "rob": [[[True, "user"]], "Rob someone"],
      "flip": [[[True, "side"], [True, "amount"]], "Flip a coin; double or nothing"],
      "hangman": [[], "Play a game of hangman"],
      "daily": [[], "Claim your daily coins"],
      "trivia": [[[False, "rounds"]], "Start a game of trivia"],
      "makequestion": [[], "Create a trivia question"]
    }
  },
  {
    "name": "Trade Cards",
    "description": "Commands regarding the Study Fam trade cards.",
    "aliases": ["cards"],
    "commands": {
      "packshop": [[], "Displays the trade card pack shop"],
      "buypack": [[[True, "card pack"]], "Buy a card pack from the pack shop"],
      "mycards": [[], "Shows a list of your trade cards"],
      "cardinfo": [[[True, "card name"]], "Show information about a trade card"],
      "mergecards": [[], "Merge some trade cards in exchange for a better card"],
      "sellcard": [[[True, "card name"]], "Sell a trade card for coins"],
      "trade": [[[True, "user"]], "Trade cards with someone"]
    }
  }
]