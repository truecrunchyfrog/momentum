from discord import FFmpegPCMAudio

savedSounds = []
soundsData = []

def GetSound(location):
    if location in savedSounds:
      return soundsData[savedSounds.index(location)]
    else:
      soundsData.append(FFmpegPCMAudio(location))
      return soundsData[-1]