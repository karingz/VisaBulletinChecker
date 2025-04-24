from VisaBulletinChecker import run_check


def handler(request):
    result, bulletin_month = run_check(return_month=True)
    return {
        "statusCode": 200,
        "body": {
            "result": result,
            "bulletin_month": bulletin_month
        }
    }