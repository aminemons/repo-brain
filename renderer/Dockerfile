FROM mcr.microsoft.com/dotnet/sdk:10.0.401 AS dotnet-build
WORKDIR /src
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/XMinty77/Najm.git /src/najm \
    && git -C /src/najm checkout --detach 6e898a51c7e7e2f0992a194891491fd1253c246e \
    && test "$(git -C /src/najm rev-parse HEAD)" = 6e898a51c7e7e2f0992a194891491fd1253c246e
COPY renderer/ /src/renderer/
RUN dotnet publish /src/renderer/NajmRenderer.csproj -c Release -o /out --no-self-contained

FROM mcr.microsoft.com/dotnet/runtime:10.0 AS dotnet-runtime

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libfontconfig1 libfreetype6 libicu72 libssl3 zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system renderer \
    && useradd --system --gid renderer --home-dir /app renderer
WORKDIR /app
ENV HOME=/tmp DOTNET_CLI_HOME=/tmp/.dotnet DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
COPY --from=dotnet-runtime /usr/share/dotnet/ /usr/share/dotnet/
RUN ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet
COPY --from=dotnet-build /out/ /app/dotnet/
COPY renderer/worker.py /app/
COPY --from=dotnet-build /src/najm/LICENSE /app/notices/NAJM-LICENSE
COPY --from=dotnet-build /src/najm/THIRD-PARTY-NOTICES.md /app/notices/NAJM-THIRD-PARTY-NOTICES.md
COPY --from=dotnet-build /src/najm/src/Najm.Text/Fonts/LatinModernRoman-2.005/GUST-FONT-LICENSE.TXT /app/notices/
COPY --from=dotnet-build /src/najm/src/Najm.Text/Fonts/LatinModernMath-1.959/GUST-FONT-LICENSE.txt /app/notices/
COPY --from=dotnet-build /src/najm/src/Najm.Text/Fonts/LatinModernRoman-2.005/README-Latin-Modern.TXT /app/notices/
COPY --from=dotnet-build /src/najm/src/Najm.Text/Fonts/LatinModernMath-1.959/README-Latin-Modern-Math.txt /app/notices/
COPY --from=dotnet-build /src/najm/src/Najm.Text/Fonts/fonts.manifest.json /app/notices/
RUN chmod -R a=rX /app
USER renderer
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
ENTRYPOINT ["python", "worker.py"]
