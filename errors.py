class UnsupportedPlatformError(Exception):
    def __init__(self, platform, message="Your platform '{}' is not supported, sorry!"):
        self.platform = platform
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message.format(self.platform)
