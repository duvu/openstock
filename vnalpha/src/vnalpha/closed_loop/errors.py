class ClosedLoopError(RuntimeError):
    pass


class ClosedLoopPersistenceError(ClosedLoopError):
    pass


class ClosedLoopNotFoundError(ClosedLoopError):
    pass


class ClosedLoopBoundaryError(ClosedLoopError):
    pass


class PromotionGateError(ClosedLoopError):
    pass
