import cardauthors as ca

folderpath = "images/tradecards/"

rarities = [
  "Common", # 0
  "Uncommon", # 1
  "Rare", # 2
  "Legendary", # 3
  "God" # 4
]

rarity_chances = [
  45,
  20,
  8,
  3,
  1
]

rarity_sellfor = [
  80,
  400,
  1500,
  5000,
  15000
]

rarity_emojis = [
  "<:common:831838270987304971>",
  "<:Uncommon:831838304554450964>",
  "<:Rare:831838328067326003>",
  "<:Legendary:831838354692767775>",
  "<:God_Rarity:832185423966896159>"
]

rarity_colours = [
  0x4290f5,
  0xa50eb0,
  0xa1101f,
  0xab790e,
  0x166b12
]


tradecards = [
  {
    "name": "Doge Thalia", # 0
    "quote": "The almighty Ben. Thalia, Study Fam's creator's dog.",
    "rarity": 0,
    "image": "doge_thalia.png",
    "author": ca.shoe
  },
  {
    "name": "Long cat", # 1
    "quote": "A cat with an oddly long neck...",
    "rarity": 1,
    "image": "long_cat.png",
    "author": ca.shoe
  },
  {
    "name": "Zoom cat", # 2
    "quote": "A cat in a zoom meeting. What can go wrong?",
    "rarity": 0,
    "image": "zoom_cat.png",
    "author": ca.shoe
  },
  {
    "name": "Pop cat", # 3
    "quote": "Infinite recursion...",
    "rarity": 4,
    "image": "popcat.png",
    "author": ca.shoe
  },
  {
    "name": "Cowboy Pepe", # 4
    "quote": "Don't go near this guy.",
    "rarity": 2,
    "image": "cowboy_pepe.png",
    "author": ca.shoe
  },
  {
    "name": "Tall cat", # 5
    "quote": "Empire State Building? What's that?",
    "rarity": 0,
    "image": "tall_cat.png",
    "author": ca.anivya
  },
  {
    "name": "Petted cat", # 6
    "quote": "Cat pets human.",
    "rarity": 2,
    "image": "petted_cat.png",
    "author": ca.shoe
  },
  {
    "name": "Rubick", # 7
    "quote": "Hello Johannes!",
    "rarity": 0,
    "image": "rubick.png",
    "author": ca.shoe
  },
  {
    "name": "Fat dog", # 8
    "quote": "The real doge.",
    "rarity": 1,
    "image": "fat_dog.png",
    "author": ca.shoe
  },
  {
    "name": "Sad Pepe", # 9
    "quote": "Sad frog is valuable.",
    "rarity": 0,
    "image": "sad_pepe.png",
    "author": ca.shoe
  },
  {
    "name": "Stabby duck", # 10
    "quote": "Fly, you fools!",
    "rarity": 1,
    "image": "stabby_duck.png",
    "author": ca.anivya
  },
  {
    "name": "Muscle Pepe", # 11
    "quote": "Weird flex, bro.",
    "rarity": 0,
    "image": "muscle_pepe.png",
    "author": ca.shoe
  },
  {
    "name": "Val", # 12
    "quote": "Valouzee?",
    "rarity": 0,
    "image": "valouzee.png",
    "author": ca.shoe
  },
  {
    "name": "Baby Yoda", # 13
    "quote": "AKA Grogu. Good coffee.",
    "rarity": 2,
    "image": "baby_yoda.png",
    "author": ca.anivya
  },
  {
    "name": "Catto blush", # 14
    "quote": "Blushed cat.",
    "rarity": 0,
    "image": "baka_cat.png",
    "author": ca.anivya
  },
  {
    "name": "Is this a pigeon?", # 15
    "quote": "Is it?",
    "rarity": 0,
    "image": "is_this_a_pigeon.png",
    "author": ca.archetim
  },
  {
    "name": "a", # 16
    "quote": "Frog says a.",
    "rarity": 0,
    "image": "a.jpg",
    "author": ca.amelia
  },
  {
    "name": "Heh", # 17
    "quote": "Cat laughs.",
    "rarity": 2,
    "image": "heh.png",
    "author": ca.amelia
  },
  {
    "name": "Grr", # 18
    "quote": "Cat grrs.",
    "rarity": 1,
    "image": "grr.png",
    "author": ca.amelia
  },
  {
    "name": "Inhaling seagull", # 19
    "quote": "Phhhh... AAAAAAAAAA!!!",
    "rarity": 1,
    "image": "inhaling_seagull_fixed.png",
    "author": ca.anivya
  },
  {
    "name": "Nelson", # 20
    "quote": "Nelson VS Linus Sebastian. Who would win?",
    "rarity": 1,
    "image": "linus_tech_tips.png",
    "author": ca.amelia
  },
  {
    "name": "Honk", # 21
    "quote": "Peace was never an option.",
    "rarity": 2,
    "image": "honk.png",
    "author": ca.amelia
  },
  {
    "name": "Borgar cat", # 22
    "quote": "wat u want from macdondal\n\n\n\nborgar",
    "rarity": 3,
    "image": "borgar_cat.png",
    "author": ca.amelia
  },
  {
    "name": "Loops", # 23
    "quote": "bröther may i have some lööps",
    "rarity": 2,
    "image": "loops_fixed.png",
    "author": ca.anivya
  },
  {
    "name": "Scroll of Truth", # 24
    "quote": "I don't need sleep, I need humor.",
    "rarity": 1,
    "image": "scroll_of_truth.png",
    "author": ca.anivya
  },
  {
    "name": "This is fine", # 25
    "quote": "Exam is just tomorrow, no problem!",
    "rarity": 2,
    "image": "this_is_fine_fixed.png",
    "author": ca.anivya
  },
  {
    "name": "Entire circus", # 26
    "quote": "Objection!",
    "rarity": 1,
    "image": "entire_circus.png",
    "author": ca.archetim
  },
  {
    "name": "angry as fuk", # 27
    "quote": "A rare case of please don't pet right now.",
    "rarity": 4,
    "image": "cat_weird_arms.gif",
    "author": ca.shoe
  },
  {
    "name": "Mocking Spongebob", # 28
    "quote": "You are being mocked by a sponge.",
    "rarity": 0,
    "image": "mocking_spongebob.png",
    "author": ca.anivya
  },
  {
    "name": "Scared Hamster", # 29
    "quote": "You scared the hamster, congraulations!",
    "rarity": 0,
    "image": "scared_hamster.png",
    "author": ca.anivya
  },
  {
    "name": "tired As Sh*t", # 30
    "quote": "The not so rare case of escalating power naps.",
    "rarity": 4,
    "image": "tired_as_shit.gif",
    "author": ca.anivya
  },
  {
    "name": "Confused As Hek", # 31
    "quote": "A case of Confusion of da highest Orda.",
    "rarity": 4,
    "image": "confused_as_hek.png",
    "author": ca.archetim
  },
  {
    "name": "Noted", # 32
    "quote": "Kowalski, status report.",
    "rarity": 0,
    "image": "noted.png",
    "author": ca.archetim
  },
  {
    "name": "Lie Down Cry A Lot", # 33
    "quote": "F as in my grades.",
    "rarity": 1,
    "image": "lie_down_cry_a_lot.png",
    "author": ca.archetim
  },
  {
    "name": "Is For Me?", # 34
    "quote": "-touches fingers-",
    "rarity": 0,
    "image": "is_for_me.png",
    "author": ca.anivya
  },
  {
    "name": "Why Always Wear That Mask?", # 35
    "quote": "Let's pretend I didnt see that",
    "rarity": 2,
    "image": "why_wear_mask.png",
    "author": ca.archetim
  },
  {
    "name": "Glass Cat", # 36
    "quote": "I am happy with what you have given me today.\nPlease return tomorrow.",
    "rarity": 1,
    "image": "glass_cat.png",
    "author": ca.shoe
  },
  {
    "name": "Spooked", # 37
    "quote": "Spooky...",
    "rarity": 1,
    "image": "spooked.png",
    "author": ca.shoe
  },
  {
    "name": "Trade Offer!!!", # 38
    "quote": "It's a deal.",
    "rarity": 0,
    "image": "trade_offer.png",
    "author": ca.shoe
  },
  {
    "name": "Who Knocked Over My Onions", # 39
    "quote": "Onion",
    "rarity": 0,
    "image": "who_knocked_over_my_onions.png",
    "author": ca.shoe
  },
  {
    "name": "Stonks", # 40
    "quote": "Studying efficiency!!!!1!!1!1",
    "rarity": 0,
    "image": "stonks.png",
    "author": ca.archetim
  },
  {
    "name": "Crow Of Judgement", # 41
    "quote": "The crow is judging you. Verdict pending.",
    "rarity": 0,
    "image": "crow_of_judgement.png",
    "author": ca.archetim
  },
  {
    "name": "Procrastination 100", # 42
    "quote": "Don't get lost in sidequests...",
    "rarity": 1,
    "image": "procrastination_100.png",
    "author": ca.archetim
  },
  {
    "name": "Anivya", # 43
    "quote": "animalnd crosng",
    "rarity": 3,
    "image": "gift.png",
    "author": ca.shoe
  },
  {
    "name": "Rice", # 44
    "quote": "Three in one.",
    "rarity": 0,
    "image": "rice.png",
    "author": ca.archetim
  },
]



packs = {
  "memes": {
    "cost": 1400,
    "cards": [0, 4, 7, 8, 9, 10, 11, 12, 13, 15, 16, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 40, 41, 42, 43, 44],
    "description": "Cards of internet culture and memes. They are funny."
  },
  "cats": {
    "cost": 1600,
    "cards": [1, 2, 3, 5, 6, 14, 17, 18, 22, 23, 36, 37, 38, 39],
    "description": "Yes. We have so many cat cards that we have an entire pack for it. Some cats from this pack are actually memes. 100% chance of getting a cat, get one now!"
  },
  "fanart": {
    "cost": 700,
    "cards": [],
    "description": "Contains cards that resemble people (or animals) here on Study Fam! Fan-art?"
  }
}