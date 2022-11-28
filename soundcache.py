from discord import FFmpegPCMAudio

savedSounds = []
soundsData = []

def GetSound(location):
    if location in savedSounds:
      return soundsData[savedSounds.index(location)]
    else:
      soundsData.append(FFmpegPCMAudio(location, before_options="-guess_layout_max 0"))
      return soundsData[-1]