"""
AWS Lambda Handlers
Entry points for Lambda functions
"""

import asyncio
from mangum import Mangum
from app.main import app

# Main API handler (API Gateway -> Lambda)
handler = Mangum(app, lifespan="off")


def cleanup_handler(event, context):
    """
    Lambda handler for expired booking cleanup.
    Triggered by EventBridge every 1 minute.
    """
    from app.jobs import cleanup_expired_bookings
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(cleanup_expired_bookings())
    
    return {
        "statusCode": 200,
        "body": result
    }


def stale_holds_cleanup_handler(event, context):
    """
    Lambda handler for stale hold references cleanup.
    Triggered by EventBridge every 2 minutes.
    
    Cleans up car:holds:* sets where the hold:{id} key has expired.
    """
    from app.jobs import cleanup_stale_holds
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(cleanup_stale_holds())
    
    return {
        "statusCode": 200,
        "body": result
    }


def reconciliation_handler(event, context):
    """
    Lambda handler for payment reconciliation.
    Triggered by EventBridge every 10 minutes.
    """
    from app.jobs import reconcile_pending_payments
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(reconcile_pending_payments())
    
    return {
        "statusCode": 200,
        "body": result
    }


def schedule_refresh_handler(event, context):
    """
    Lambda handler for cache refresh.
    Triggered by EventBridge every 5 minutes.
    """
    from app.jobs import refresh_car_schedules
    
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(refresh_car_schedules())
    
    return {
        "statusCode": 200,
        "body": result
    }
