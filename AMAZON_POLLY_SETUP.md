# Amazon Polly TTS Setup Guide

This document explains how to configure and verify Amazon Polly text-to-speech functionality in A.L.F.R.E.D.'s voice interface, which has replaced the previous Azure TTS integration.

## Prerequisites

1. **AWS Account**: You need an active AWS account with Amazon Polly access
2. **Python Dependencies**: boto3 is required (automatically installed with requirements.txt)
3. **Audio Playback**: pygame is used for audio playback (already in requirements)

## AWS Configuration

### 1. Create AWS IAM User

1. Log into AWS Management Console
2. Navigate to IAM → Users → Add User
3. Create a user with programmatic access
4. Attach the `AmazonPollyReadOnlyAccess` policy (or create custom policy)

### 2. Get AWS Credentials

After creating the user, you'll receive:
- **Access Key ID**
- **Secret Access Key**

### 3. Set Environment Variables

Configure your environment with AWS credentials:

```bash
# Required
export AWS_ACCESS_KEY_ID='your-access-key-id'
export AWS_SECRET_ACCESS_KEY='your-secret-access-key'

# Optional (defaults to us-east-1)
export AWS_REGION='us-east-1'
```

### 4. Alternative: AWS Credentials File

Instead of environment variables, you can use AWS credentials file:

```bash
# Create ~/.aws/credentials
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
region = us-east-1
```

## Voice Configuration

The A.L.F.R.E.D. voice interface uses:
- **Voice ID**: Brian (British male neural voice)
- **Engine**: neural (for high quality)
- **Output Format**: mp3
- **Region**: us-east-1 (default, configurable)

## Verification Steps

### Step 1: Test Dependencies

```bash
python -c "import boto3, pygame; print('✅ All dependencies available')"
```

### Step 2: Run Test Script

```bash
python test_polly.py
```

This script will:
1. ✅ Test AWS connection
2. ✅ Verify credentials  
3. ✅ Test speech synthesis
4. ✅ Test audio playback
5. ✅ Clean up temporary files

### Step 3: Test Voice Interface

```bash
# Start the A.L.F.R.E.D. voice interface
python -m coordinator.web.interface
```

The voice interface should:
1. Display "Amazon Polly TTS initialized successfully" in logs
2. Use text-to-speech for responses
3. Show "🔊 Echoing through the bat cave..." when speaking

## Troubleshooting

### Common Issues

#### 1. Missing AWS Credentials
```
❌ ERROR: Missing AWS credentials!
```
**Solution**: Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables

#### 2. Invalid Credentials
```
❌ ERROR: Failed to connect to Amazon Polly: The AWS Access Key Id you provided does not exist in our records.
```
**Solution**: Verify your AWS credentials are correct

#### 3. Insufficient Permissions
```
❌ ERROR: User is not authorized to perform: polly:SynthesizeSpeech
```
**Solution**: Add AmazonPollyReadOnlyAccess policy to your IAM user

#### 4. Region Issues
```
❌ ERROR: Could not connect to the endpoint URL
```
**Solution**: Verify your AWS_REGION is supported by Polly

#### 5. Audio Playback Issues
```
❌ ERROR: pygame.error: No audio device available
```
**Solution**: Ensure your system has audio capabilities or run in headless mode

### Fallback Behavior

If Amazon Polly fails, A.L.F.R.E.D. will:
1. Display warning: "🔇 Amazon Polly not configured, using text only"
2. Continue operating with text-only responses
3. Log detailed error information

## Cost Considerations

Amazon Polly pricing (as of 2025):
- **Neural voices**: $16.00 per 1M characters
- **Standard voices**: $4.00 per 1M characters
- **Free tier**: 5M characters per month for 12 months

The voice interface typically uses ~50-100 characters per response.

## Available Voices

Popular male voices for Batman-themed interface:
- **Brian** (British male, neural) - Currently used
- **Matthew** (US male, neural)  
- **Arthur** (British male, neural)
- **Daniel** (German male, neural)

To change voice, edit `self.voice_id = 'Brian'` in `coordinator/voice/interface.py:98`.

## Security Best Practices

1. **Environment Variables**: Never hardcode AWS credentials in source code
2. **IAM Permissions**: Use principle of least privilege
3. **Key Rotation**: Regularly rotate AWS access keys
4. **Monitoring**: Enable AWS CloudTrail for API monitoring

## Migration from Azure TTS

### Changes Made:
1. Replaced `azure-cognitiveservices-speech` with `boto3`
2. Updated environment variables from `AZURE_SPEECH_*` to `AWS_*`
3. Changed voice from "en-GB-RyanNeural" to "Brian"
4. Modified audio playback to use temporary files + pygame

### Environment Variable Migration:
```bash
# Old (Azure)
AZURE_SPEECH_KEY='...'
AZURE_SPEECH_REGION='eastus'

# New (Amazon Polly)  
AWS_ACCESS_KEY_ID='...'
AWS_SECRET_ACCESS_KEY='...'
AWS_REGION='us-east-1'
```

## Support

If you encounter issues:
1. Run `python test_polly.py` for diagnosis
2. Check logs for detailed error messages
3. Verify AWS console for API call logs
4. Ensure audio system is working: `python -c "import pygame; pygame.mixer.init(); print('Audio OK')"`

The voice interface will gracefully degrade to text-only mode if TTS fails, ensuring A.L.F.R.E.D. remains functional even without speech capabilities.