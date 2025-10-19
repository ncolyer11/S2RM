package com.github.winplay02.gitcraft.signatures.ornithe;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.file.FileSystem;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

import com.github.winplay02.gitcraft.pipeline.GitCraftPipelineFilesystemRoot;
import com.github.winplay02.gitcraft.pipeline.GitCraftPipelineFilesystemStorage;
import com.github.winplay02.gitcraft.pipeline.IStepContext;
import com.github.winplay02.gitcraft.pipeline.key.MinecraftJar;
import com.github.winplay02.gitcraft.signatures.SignaturesPatch;
import com.github.winplay02.gitcraft.GitCraft;
import com.github.winplay02.gitcraft.meta.GameVersionBuildMeta;
import com.github.winplay02.gitcraft.meta.MetaUrls;
import com.github.winplay02.gitcraft.meta.RemoteVersionMetaSource;
import com.github.winplay02.gitcraft.meta.VersionMetaSource;
import com.github.winplay02.gitcraft.pipeline.StepStatus;
import com.github.winplay02.gitcraft.types.OrderedVersion;
import com.github.winplay02.gitcraft.util.FileSystemNetworkManager;
import com.github.winplay02.gitcraft.util.RemoteHelper;

import com.github.winplay02.gitcraft.util.SerializationTypes;
import io.github.gaming32.signaturechanger.tree.SigsFile;
import io.github.gaming32.signaturechanger.visitor.SigsReader;

public class SparrowSignatures extends SignaturesPatch {

	private final VersionMetaSource<GameVersionBuildMeta> sparrowVersions;

	public SparrowSignatures() {
		this.sparrowVersions = new RemoteVersionMetaSource<>(
			MetaUrls.ORNITHE_SPARROW,
			SerializationTypes.TYPE_LIST_GAME_VERSION_BUILD_META,
			GameVersionBuildMeta::gameVersion
		);
	}

	private static String versionKey(OrderedVersion mcVersion, MinecraftJar minecraftJar) {
		return minecraftJar == MinecraftJar.MERGED
			? mcVersion.launcherFriendlyVersionName()
			: mcVersion.launcherFriendlyVersionName() + "-" + minecraftJar.name().toLowerCase();
	}

	private GameVersionBuildMeta getLatestSparrowVersion(OrderedVersion mcVersion, MinecraftJar minecraftJar) throws IOException, URISyntaxException, InterruptedException {
		return sparrowVersions.getLatest(versionKey(mcVersion, minecraftJar));
	}

	@Override
	public String getName() {
		return "Ornithe Sparrow";
	}

	@Override
	public boolean doSignaturesExist(OrderedVersion mcVersion) {
		return doSignaturesExist(mcVersion, MinecraftJar.CLIENT) || doSignaturesExist(mcVersion, MinecraftJar.SERVER) || doSignaturesExist(mcVersion, MinecraftJar.MERGED);
	}

	@Override
	public boolean doSignaturesExist(OrderedVersion mcVersion, MinecraftJar minecraftJar) {
		try {
			return getLatestSparrowVersion(mcVersion, minecraftJar) != null;
		} catch (IOException | URISyntaxException | InterruptedException e) {
			return false;
		}
	}

	@Override
	public boolean canSignaturesBeUsedOn(OrderedVersion mcVersion, MinecraftJar minecraftJar) {
		return (!mcVersion.hasSharedVersioning() || mcVersion.hasSharedObfuscation())
			? doSignaturesExist(mcVersion, MinecraftJar.MERGED)
			: doSignaturesExist(mcVersion, minecraftJar);
	}

	@Override
	public StepStatus provideSignatures(IStepContext<?, OrderedVersion> versionContext, MinecraftJar minecraftJar) throws IOException, URISyntaxException, InterruptedException {
		GameVersionBuildMeta sparrowVersion = getLatestSparrowVersion(versionContext.targetVersion(), minecraftJar);
		if (sparrowVersion == null) {
			return StepStatus.NOT_RUN;
		}
		Path signaturesFile = getSignaturesPathInternal(versionContext.targetVersion(), minecraftJar);
		if (Files.exists(signaturesFile) && validateSignatures(signaturesFile)) {
			return StepStatus.UP_TO_DATE;
		}
		Files.deleteIfExists(signaturesFile);
		Path signaturesJarFile = getSignaturesJarPath(versionContext.targetVersion(), minecraftJar);
		StepStatus downloadStatus = RemoteHelper.downloadToFileWithChecksumIfNotExistsNoRetryMaven(versionContext.executorService(), sparrowVersion.makeJarMavenUrl(GitCraft.ORNITHE_MAVEN), new FileSystemNetworkManager.LocalFileInfo(signaturesJarFile, null, null, "ornithe sparrow", versionContext.targetVersion().launcherFriendlyVersionName()));
		try (FileSystem fs = FileSystems.newFileSystem(signaturesJarFile)) {
			Path signaturesPathInJar = fs.getPath("signatures", "mappings.sigs");
			Files.copy(signaturesPathInJar, signaturesFile, StandardCopyOption.REPLACE_EXISTING);
		}
		return StepStatus.merge(downloadStatus, StepStatus.SUCCESS);
	}

	@Override
	protected Path getSignaturesPathInternal(OrderedVersion mcVersion, MinecraftJar minecraftJar) {
		try {
			GameVersionBuildMeta sparrowVersion = getLatestSparrowVersion(mcVersion, minecraftJar);
			if (sparrowVersion == null) {
				return null;
			}
			return sparrowVersion == null ? null : GitCraftPipelineFilesystemRoot.getPatchesStore().apply(GitCraftPipelineFilesystemStorage.DEFAULT.get().rootFilesystem()).resolve(String.format("%s-ornithe-sparrow-build.%d.sigs", versionKey(mcVersion, minecraftJar), sparrowVersion.build()));
		} catch (IOException | URISyntaxException | InterruptedException e) {
			return null;
		}
	}

	private Path getSignaturesJarPath(OrderedVersion mcVersion, MinecraftJar minecraftJar) {
		try {
			GameVersionBuildMeta sparrowVersion = getLatestSparrowVersion(mcVersion, minecraftJar);
			if (sparrowVersion == null) {
				return null;
			}
			return sparrowVersion == null ? null : GitCraftPipelineFilesystemRoot.getPatchesStore().apply(GitCraftPipelineFilesystemStorage.DEFAULT.get().rootFilesystem()).resolve(String.format("%s-ornithe-sparrow-build.%d.jar", versionKey(mcVersion, minecraftJar), sparrowVersion.build()));
		} catch (IOException | URISyntaxException | InterruptedException e) {
			return null;
		}
	}

	@Override
	public void visit(OrderedVersion mcVersion, MinecraftJar minecraftJar, SigsFile visitor) throws IOException {
		if (!mcVersion.hasSharedVersioning() || mcVersion.hasSharedObfuscation()) {
			minecraftJar = MinecraftJar.MERGED;
		}
		Path sigsPath = getSignaturesPathInternal(mcVersion, minecraftJar);
		try (SigsReader sr = new SigsReader(Files.newBufferedReader(sigsPath))) {
			sr.accept(visitor);
		}
	}
}
