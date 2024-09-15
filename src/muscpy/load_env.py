#!/bin/env python3
import os
import re


def get_all_envs(env_file_path: str) -> dict[str, str]:
    pattern = re.compile(r"([\S]+)=([\"'][\S]+[\"']|[\S]+)")
    envs: dict[str, str] = {}

    # Read from the .env file
    try:
        with open(env_file_path) as env_file:
            lines = env_file.read()
        raw: list[str | tuple[str, str]] = pattern.findall(lines)
        for i in raw:
            if isinstance(i, tuple):
                splitted_env = i
            else:
                splitted_env = i.split("=")
            envs[splitted_env[0]] = splitted_env[1].strip('"')
    except FileNotFoundError:
        print(
            f"Warning: The file {env_file_path} was not found. Proceeding with environment variables only."
        )

    return envs


def get_env(env_name: str, env_file_path: str) -> str:
    # First, check if the environment variable is set
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value

    # If not found, check the .env file
    all_env = get_all_envs(env_file_path)
    return all_env.get(env_name, None)  # Return None if the env variable is not found


# Example usage
# env_value = get_env('MY_ENV_VAR', '.env')
# print(env_value)
