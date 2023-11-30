import logging

class BaseHandler:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.getLevelName(self.config.log_level))
        self.logger.info("Logger for %s initialized", self.__class__.__name__)

    async def handle(self, message, bot):
        raise NotImplementedError("This method should be implemented by subclasses.")
