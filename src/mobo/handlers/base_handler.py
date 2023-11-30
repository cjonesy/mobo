class BaseHandler:
    async def handle(self, message, bot):
        raise NotImplementedError("This method should be implemented by subclasses.")
