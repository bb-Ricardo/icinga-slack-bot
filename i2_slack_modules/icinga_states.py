####
#
# define and describe Icinga state types
#

icinga_state_types = [
    {
        "name": "UP",
        "object": "Host",
        "value": 0,
        "color": "good",
        "icon": ":white_check_mark:"
    },
    {
        "name": "DOWN",
        "object": "Host",
        "value": 1,
        "color": "danger",
        "icon": ":red_circle:"
    },
    {
        "name": "UNREACHABLE",
        "object": "Host",
        "value": 2,
        "color": "#BC1414",
        "icon": ":octagonal_sign:"
    },
    {
        "name": "OK",
        "object": "Service",
        "value": 0,
        "color": "good",
        "icon": ":white_check_mark:"
    },
    {
        "name": "WARNING",
        "object": "Service",
        "value": 1,
        "color": "warning",
        "icon": ":warning:"
    },
    {
        "name": "CRITICAL",
        "object": "Service",
        "value": 2,
        "color": "danger",
        "icon": ":red_circle:"
    },
    {
        "name": "UNKNOWN",
        "object": "Service",
        "value": 3,
        "color": "#E066FF",
        "icon": ":question:"
    }
]


class IcingaStates:
    """
    A class used to represent all valid Icinga states and
    return all properties on each state if requested.

    This will represent the list 'icinga_state_types' as
    a class and each state as a attribute.
    """

    class _SingleState:
        """
        This subclass meant to hold a single Icinga state
        and turns a state dict into an object with
        attributes defined in state dict keys
        """
        def __init__(self, dictionary: dict) -> None:
            """Constructor"""
            for key in dictionary:
                setattr(self, key, dictionary[key])

        def __repr__(self) -> str:
            return str(self.__dict__)

    def __init__(self) -> None:
        """
        Iterate over the list of dictionaries (icinga_state_types)
        and set each state name as attribute with _SingleState as value
        """
        for state in icinga_state_types:
            setattr(self, state.get("name"), self._SingleState(state))

    def value(self, state_value: int, object_type: str) -> _SingleState:
        """
        Returns a icinga _SingleState for a value (i.e: 2) and a
        object_type (i.e. Service).

        Parameters
        ----------
        state_value: int
            value of the state to get
        object_type: str
            object type of the state to get (Host, Service)

        Returns
        -------
        _SingleState: with the state searched for
        """
        for state in self:
            if state.value == state_value and state.object == object_type:
                return state

    def name(self, name: str) -> _SingleState:
        """
        Return a _SingleState based on the given 'name'

        Parameters
        ----------
        name: str
            name of the state to return (i.e.: UP)

        Returns
        -------
        _SingleState: with the state searched for
        """
        try:
            return getattr(self, name.upper())
        except AttributeError:
            pass

    def __repr__(self) -> str:
        return str(self.__dict__)

    def __iter__(self) -> _SingleState:
        for state in self.__dict__:
            yield getattr(self, state)
