**Scoring API with authentification.**

Based on built in standard python library http.server, so it is not recommended for production. It only implements basic security checks.

To run tests

$ python3 test.py

to run API server

$ python3 api.py

**Protocol description**

Request
Fields (common for all methods):
- account - string, optional, can be empty
- login - string, required, can be empty
- token - string, required, can be empty
- method - string, required, can be empty
- arguments - dict (json object), required, can be empty

Request is valid if every field is valid

Responses:

- {"code": number, "response": {method response}}

OR on errors

- {"code": number, "error": {error message}}

**Methods**:

**_online_score_.**

    Arguments fields
    - phone - should be str or int type, should be 11 characters long and start with 7, optional, can be empty
    - email - at least should consist @, can be empty
    - first_name - string, can be empty
    - last_name - string, can be empty
    - birthday - format DD.MM. YYYY, can be empty
    - gender - integer 0, 1 or 2, can be empty

    Arguments are valid if every field is valid. 

    One of the pair should exist in request, and should be not empty:

    - phone / email
    - first_name / last_name,
    - gender / birthday

    Context: It should has a "has" field representing the number of not empty argumet fields.

    Response
    if authentication and validation succeeds

    - {"score": number}

    OR from authenticated admin

    - {"score": 42}

    OR on error

    - {"code": 422, "error": message}

    Example

    $ curl -X POST  -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95", "arguments": {"email": "example@example.com", "first_name":"unknown", "last_name": "", "birthday": "01.01.2000", "gender": 1}}' http://127.0.0.1:8080/method/

    Response:

    {"response": {"score": 3.0}, "code": 200}


**_clients_interests_**

    Arguments fields
    - client_ids - list of numbers, required, not empty
    - date - format DD.MM. YYYY, optional, can be empty

    {"client_ids": [1,2,3,4], "date": "04.10.2023"}

    Arguments are valid if every field is valid

    Response

    {"client_id1": ["interest1", "interest2" ...], "client2": [...] ...}

    Context: It should have a "nclients" field representing the number of "interests" of the identifiers.

    Example

    $ curl -X POST  -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95", "arguments": {"client_ids": [1,2,3,4], "date": "04.10.2023"}}' http://127.0.0.1:8080/method/

    Response:

    {"response": {"1": ["cars", "geek"], "2": ["music", "travel"], "3": ["books", "hi-tech"], "4": ["geek", "music"]}, "code": 200}

