import logging
import boto3
from botocore.config import Config
from watchtower import CloudWatchLogHandler

# Create a CloudWatch Logs client with a custom configuration
logs_client = boto3.client(
    "logs",
    region_name="us-east-1",
    config=Config(retries={'max_attempts': 10})
)


# Setup logging formatter
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

# Initialize the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Check if CloudWatchLogHandler is already in logger.handlers to avoid duplicates
if not any(isinstance(h, CloudWatchLogHandler) for h in logger.handlers):
    # Initialize CloudWatch handler with a default stream name and add it to logger
    cloudwatch_handler = CloudWatchLogHandler(log_group_name="OvaDriveAppLogs", log_stream_name="default",
    boto3_client=logs_client)
    cloudwatch_handler.setFormatter(formatter)
    logger.addHandler(cloudwatch_handler)

# Define a function to update the log stream name and log messages
def log_to_cloudwatch(level, text, stream):
    """
    Logs a message to AWS CloudWatch logs with the specified level and stream.

    Args:
        level (str): The log level ('info', 'error', 'critical').
        text (str): The log message.
        stream (str): The CloudWatch log stream name.
    """
    # Get the CloudWatch handler from the logger
    for handler in logger.handlers:
        if isinstance(handler, CloudWatchLogHandler):
            # Update the CloudWatch handler's log stream name if it has changed
            if getattr(handler, 'log_stream_name', '') != stream:
                handler.log_stream_name = stream
                # Re-attach the handler to apply the new log stream name
                logger.removeHandler(handler)
                logger.addHandler(handler)
            break  # Assuming there's only one CloudWatchLogHandler

    # Log the message
    if level == 'info':
        logger.info(text)
    elif level == 'error':
        logger.error(text)
    elif level == 'critical':
        logger.critical(text)

# Function to log info messages
def info(text, stream):
    log_to_cloudwatch('info', text, stream)

# Function to log error messages
def error(text, stream):
    log_to_cloudwatch('error', text, stream)

# Function to log critical messages
def critical(text, stream):
    log_to_cloudwatch('critical', text, stream)