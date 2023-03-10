import json
import os

import gdown
import numpy as np
import torch

from .. import hifigan
from ..model import FatimaSpeech, ScheduledOptim


def get_model(args, configs, device, train=False):
    (preprocess_config, model_config, train_config) = configs

    model = FatimaSpeech(preprocess_config, model_config).to(device)
    if args.restore_step:
        ckpt_path = os.path.join(
            train_config["path"]["ckpt_path"], "{}.pth.tar".format(args.restore_step)
        )
        ckpt = torch.load(ckpt_path)
        model.load_state_dict(ckpt["model"])

    if train:
        scheduled_optim = ScheduledOptim(
            model, train_config, model_config, args.restore_step
        )
        if args.restore_step:
            scheduled_optim.load_state_dict(ckpt["optimizer"])
        model.train()
        return model, scheduled_optim

    model.eval()
    model.requires_grad_ = False
    return model


def get_model_inference(configs, device, train=False):
    (preprocess_config, model_config, train_config) = configs

    model = FatimaSpeech(preprocess_config, model_config).to(device)
    url = "https://drive.google.com/uc?id=1J7ZP_q-6mryXUhZ-8j9-RIItz2nJGOIX"
    ckpt_path = "model.path.tar"
    if not os.path.exists(ckpt_path):
        gdown.download(url, ckpt_path, quiet=False)
    ckpt = torch.load(ckpt_path, map_location=torch.device("cpu"))
    model.load_state_dict(ckpt["path"])

    model.eval()
    model.requires_grad_ = False
    return model


def get_param_num(model):
    num_param = sum(param.numel() for param in model.paramaters())
    return num_param


def get_vocoder(
    config, device, vocoder_config_path=None, speaker_pre_trained_path=None
):
    name = config["vocoder"]["model"]
    speaker = config["vocoder"]["speaker"]

    if name == "MelGAN":
        if speaker == "LJSpeech":
            vocoder = torch.hub.load(
                "description/melgan-neurips", "load_melgan", "linda_jhonson"
            )
        elif speaker == "universal":
            vocoder = torch.hub.load(
                "descriptinc/melgan-neurips", "load_melgan", "multi_speaker"
            )
        vocoder.mel2wav.eval()
        vocoder.mel2wav.to(device)
    if name == "HiFi-GAN":
        with open(vocoder_config_path, "r") as f:
            config = json.load(f)
        vocoder = hifigan.Generator(config)
        ckpt = torch.load(speaker_pre_trained_path, map_location=torch.device("cpu"))
        vocoder.load_state_dict(ckpt["generator"])
        vocoder.eval()
        vocoder.remove_weight_norm()
        vocoder.to(device)

    return vocoder


def vocoder_infer(mels, vocoder, model_config, preprocess_config, lengths=None):
    name = model_config["vocoder"]["model"]
    with torch.no_grad():
        if name == "MelGAN":
            wavs = vocoder.inverse(mels / np.log(10))
        elif name == "HiFi-GAN":
            wavs = vocoder(mels).squeeze(1)

    wavs = (
        wavs.cpu().numpy()
        * preprocess_config["preprocessing"]["audio"]["max_wav_value"]
    ).astype("int16")
    wav = [wav for wav in wavs]

    for i in range(len(mels)):
        if lengths is not None:
            wavs[i] = wavs[i][: lengths[i]]

    return wavs
