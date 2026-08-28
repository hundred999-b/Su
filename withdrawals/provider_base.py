from abc import ABC, abstractmethod


class PayoutProviderError(Exception):
    pass


class PayoutProvider(ABC):
    name = ""

    @abstractmethod
    def create_recipient(self, *, user, destination):
        raise NotImplementedError

    @abstractmethod
    def initiate(self, *, withdrawal):
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, *, raw_body, signature="", headers=None):
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, *, payload):
        raise NotImplementedError
