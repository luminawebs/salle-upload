from config.settings import Config

def _export_strip_colon(text):
    if Config.ENABLE_INFOGRAFIA_EXPORT and text:
        return text.rstrip(":").strip()
    return text


