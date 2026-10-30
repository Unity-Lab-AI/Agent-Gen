"""Unity's vocoder, trained from random weights: log-mel (80 x T, hop 256) -> 24 kHz waveform.

HiFi-GAN V1 layout (Kong et al. 2020): a generator of transposed convolutions with multi-receptive-field
residual blocks, judged by a multi-period and a multi-scale discriminator.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils import weight_norm, spectral_norm

LRELU = 0.1


class ResBlock(nn.Module):
    def __init__(self, ch, k, dil):
        super().__init__()
        self.c1 = nn.ModuleList(weight_norm(nn.Conv1d(ch, ch, k, dilation=d, padding=(k * d - d) // 2)) for d in dil)
        self.c2 = nn.ModuleList(weight_norm(nn.Conv1d(ch, ch, k, padding=(k - 1) // 2)) for _ in dil)

    def forward(self, x):
        for a, b in zip(self.c1, self.c2):
            x = x + b(F.leaky_relu(a(F.leaky_relu(x, LRELU)), LRELU))
        return x


class Generator(nn.Module):
    def __init__(self, n_mels=80, ch=512, rates=(8, 8, 2, 2), kernels=(16, 16, 4, 4),
                 rk=(3, 7, 11), rd=((1, 3, 5), (1, 3, 5), (1, 3, 5))):
        super().__init__()
        self.pre = weight_norm(nn.Conv1d(n_mels, ch, 7, padding=3))
        self.ups, self.res = nn.ModuleList(), nn.ModuleList()
        for i, (r, k) in enumerate(zip(rates, kernels)):
            self.ups.append(weight_norm(nn.ConvTranspose1d(ch // 2 ** i, ch // 2 ** (i + 1), k, r, padding=(k - r) // 2)))
            self.res.append(nn.ModuleList(ResBlock(ch // 2 ** (i + 1), kk, dd) for kk, dd in zip(rk, rd)))
        self.post = weight_norm(nn.Conv1d(ch // 2 ** len(rates), 1, 7, padding=3))

    def forward(self, mel):
        x = self.pre(mel)
        for up, blocks in zip(self.ups, self.res):
            x = up(F.leaky_relu(x, LRELU))
            x = sum(b(x) for b in blocks) / len(blocks)
        return torch.tanh(self.post(F.leaky_relu(x)))


class PeriodD(nn.Module):
    def __init__(self, p):
        super().__init__()
        self.p = p
        chs = [1, 32, 128, 512, 1024]
        self.convs = nn.ModuleList(weight_norm(nn.Conv2d(chs[i], chs[i + 1], (5, 1), (3, 1), padding=(2, 0))) for i in range(4))
        self.convs.append(weight_norm(nn.Conv2d(1024, 1024, (5, 1), 1, padding=(2, 0))))
        self.out = weight_norm(nn.Conv2d(1024, 1, (3, 1), 1, padding=(1, 0)))

    def forward(self, x):
        b, c, t = x.shape
        if t % self.p:
            x = F.pad(x, (0, self.p - t % self.p), "reflect")
        x = x.view(b, c, -1, self.p)
        feats = []
        for conv in self.convs:
            x = F.leaky_relu(conv(x), LRELU); feats.append(x)
        x = self.out(x); feats.append(x)
        return x.flatten(1), feats


class ScaleD(nn.Module):
    def __init__(self, norm=weight_norm):
        super().__init__()
        self.convs = nn.ModuleList([
            norm(nn.Conv1d(1, 128, 15, 1, padding=7)), norm(nn.Conv1d(128, 128, 41, 2, groups=4, padding=20)),
            norm(nn.Conv1d(128, 256, 41, 2, groups=16, padding=20)), norm(nn.Conv1d(256, 512, 41, 4, groups=16, padding=20)),
            norm(nn.Conv1d(512, 1024, 41, 4, groups=16, padding=20)), norm(nn.Conv1d(1024, 1024, 41, 1, groups=16, padding=20)),
            norm(nn.Conv1d(1024, 1024, 5, 1, padding=2))])
        self.out = norm(nn.Conv1d(1024, 1, 3, 1, padding=1))

    def forward(self, x):
        feats = []
        for conv in self.convs:
            x = F.leaky_relu(conv(x), LRELU); feats.append(x)
        x = self.out(x); feats.append(x)
        return x.flatten(1), feats


class Discriminators(nn.Module):
    def __init__(self):
        super().__init__()
        self.ds = nn.ModuleList([PeriodD(p) for p in (2, 3, 5, 7, 11)] + [ScaleD(spectral_norm), ScaleD(), ScaleD()])
        self.pools = [None] * 5 + [nn.Identity(), nn.AvgPool1d(4, 2, padding=2), nn.Sequential(nn.AvgPool1d(4, 2, padding=2), nn.AvgPool1d(4, 2, padding=2))]

    def forward(self, x):
        outs = []
        for d, pool in zip(self.ds, self.pools):
            outs.append(d(pool(x) if pool is not None else x))
        return outs


def d_loss(real, fake):
    return sum(torch.mean((1 - r[0]) ** 2) + torch.mean(f[0] ** 2) for r, f in zip(real, fake))


def g_loss(fake):
    return sum(torch.mean((1 - f[0]) ** 2) for f in fake)


def fm_loss(real, fake):
    return sum(F.l1_loss(fr, rr.detach()) for r, f in zip(real, fake) for rr, fr in zip(r[1], f[1]))
