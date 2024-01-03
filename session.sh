#!/usr/local/bin/bash
set -e

# inspire from https://github.com/dewe/mfauth/blob/master/mfauth.sh

#OTP_ID=$1
#OTP=$(op item get $OTP_ID --otp)
#DEVICE_ID=$(aws iam list-mfa-devices | jq -r '.MFADevices[0].SerialNumber')
#
#RESULT=$(aws sts get-session-token --serial-number $DEVICE_ID --duration-seconds 129600 --token-code $OTP)


SESSION=$1

declare -A ROLES
ROLES=(
  # AO
  ["ao-staging"]="arn:aws:iam::409141762494:role/Developer"
  ["bidap"]="arn:aws:iam::401357991636:role/data-scientist"
  # CORE
  ["core-staging"]="arn:aws:iam::986102188572:role/developer"
  # UDP
  ["udp-ao-staging"]="arn:aws:iam::409141762494:role/adapters-developer"
)

declare -A ACCOUNTS
ACCOUNTS=(
  # AO
  ["ao-staging"]="loic.fontaine-ao"
  ["bidap"]="loic.fontaine-ao"
  # CORE
  ["core-staging"]="loic.fontaine-core"
  # UDP
  ["udp-ao-staging"]="loic.fontaine"
)

ROLE=${ROLES[${SESSION}]}
ACCOUNT=${ACCOUNTS[${SESSION}]}

# fail if role or account is not defined
if [ -z ${ROLE} ]; then
  echo "Role not defined for ${SESSION}"
  exit 1
fi
if [ -z ${ACCOUNT} ]; then
  echo "Account not defined for ${SESSION}"
  exit 1
fi

export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s" \
$(aws-vault exec ${ACCOUNT} -- aws sts assume-role \
--role-arn ${ROLE} \
--role-session-name MySessionName \
--query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]" \
--output text))

aws configure set aws_access_key_id ${AWS_ACCESS_KEY_ID} --profile ${SESSION}
aws configure set aws_secret_access_key ${AWS_SECRET_ACCESS_KEY} --profile ${SESSION}
aws configure set aws_session_token ${AWS_SESSION_TOKEN} --profile ${SESSION}
aws configure set region us-west-2 --profile ${SESSION}

#echo ${SESSION}
