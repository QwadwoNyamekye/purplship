import purplship.package as api

gateway = api.gateway["boxknight"].create(
    dict(
        username = "user-serivce-account-test",
        password = "userpassword"
    )
)