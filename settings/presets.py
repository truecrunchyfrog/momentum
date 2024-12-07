# Study earnings
SilentETokens = 5 / 60
SilentECoins = 1.8 / 60
CamETokens = 5 / 60 # 6.5 before, was normalized on meow's request
CamECoins = 2 / 60


# Study buddies
StudyBuddyOptions = [
  {
    "title": "Age range",
    "description": "Choose an age range where your age is included. You will match with people at the same range.",
    "options": [
      "< My partner's age doesn't matter >",
      "13-15 years",
      "16-18 years",
      "19-24 years",
      "25 years and older"
    ]
  },

  {
    "title": "Study schedule",
    "description": "Choose what hours you usually study, to match with someone with similar schedule.\n__Answer in UTC+0 and not any other time zone, please!__\nFind your own time zone here: https://what-is.net/my-time-zone\nIf your time zone is positive, then decrement the amount of hours to fit into UTC+0.\nIf it's negative, then increment the amount of hours to fit into UTC+0.\n\n[Here](https://www.timeanddate.com/worldclock/converter.html?iso=20220102T000000&p1=1440) is an easy way to convert your time zone to UTC+0. Just click \"Add another city or time zone\" and choose yours, then change the time in your time zone and see what it says in UTC+0.",
    "options": [
      "12pm - 3am",
      "4am - 7am",
      "8am - 11am",
      "1pm - 4pm",
      "5pm - 8pm",
      "9pm - 12pm"
    ]
  },

  {
    "title": "Academic field",
    "description": "What academic field describes what you study?",
    "options": [
      "< What my study buddy studies doesn't matter >",
      "Health sciences",
      "Computer science",
      "Engineering",
      "Psychology",
      "Natural sciences",
      "Law",
      "Linguistics",
      "Economics",
      "Business",
      "Art",
      "Mathematics",
      "< Other field >"
    ]
  }
]
