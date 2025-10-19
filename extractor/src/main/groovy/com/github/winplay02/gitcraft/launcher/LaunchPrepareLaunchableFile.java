package com.github.winplay02.gitcraft.launcher;

import com.github.winplay02.gitcraft.pipeline.GitCraftPipelineFilesystemStorage;
import com.github.winplay02.gitcraft.pipeline.GitCraftStepConfig;
import com.github.winplay02.gitcraft.pipeline.GitCraftStepWorker;
import com.github.winplay02.gitcraft.pipeline.IPipeline;
import com.github.winplay02.gitcraft.pipeline.IStepContext;
import com.github.winplay02.gitcraft.pipeline.StepInput;
import com.github.winplay02.gitcraft.pipeline.StepOutput;
import com.github.winplay02.gitcraft.pipeline.StepResults;
import com.github.winplay02.gitcraft.pipeline.StepStatus;
import com.github.winplay02.gitcraft.pipeline.key.StorageKey;
import com.github.winplay02.gitcraft.types.OrderedVersion;
import com.github.winplay02.gitcraft.util.MiscHelper;
import net.fabricmc.loom.util.FileSystemUtil;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FieldNode;
import org.objectweb.asm.tree.InnerClassNode;
import org.objectweb.asm.tree.MethodNode;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;

public record LaunchPrepareLaunchableFile(GitCraftStepConfig config) implements GitCraftStepWorker<LaunchPrepareLaunchableFile.Inputs> {

	private class ClassAccessWidenFileTransformer implements MiscHelper.PathContentTransformer {

		@Override
		public boolean shouldTransform(Path path) {
			return path.getFileName().toString().endsWith(".class") && LaunchPrepareLaunchableFile.this.config().mappingFlavour().needsPackageFixingForLaunch();
		}

		@Override
		public byte[] transform(Path path, byte[] content) {
			return transformClassToPublicAccess(content);
		}
	}

	@Override
	public StepOutput<OrderedVersion, IStepContext.SimpleStepContext<OrderedVersion>, GitCraftStepConfig> run(
		IPipeline<OrderedVersion, IStepContext.SimpleStepContext<OrderedVersion>, GitCraftStepConfig> pipeline,
		IStepContext.SimpleStepContext<OrderedVersion> context,
		LaunchPrepareLaunchableFile.Inputs input,
		StepResults<OrderedVersion, IStepContext.SimpleStepContext<OrderedVersion>, GitCraftStepConfig> results
	) throws Exception {
		Path clientOriginalPath = pipeline.getStoragePath(GitCraftPipelineFilesystemStorage.ARTIFACTS_CLIENT_JAR, context, this.config);
		Path clientModifiedPath = pipeline.getStoragePath(input.clientJar().orElse(null), context, this.config);
		Path clientOutputPath = results.getPathForKeyAndAdd(pipeline, context, this.config, GitCraftPipelineFilesystemStorage.LAUNCHABLE_CLIENT_JAR);
		Files.createDirectories(clientOutputPath.getParent());
		if (Files.exists(clientOutputPath) && !MiscHelper.isJarEmpty(clientOutputPath)) {
			return new StepOutput<>(StepStatus.UP_TO_DATE, results);
		}
		MiscHelper.PathContentTransformer classFileAccessWidenerTransform = new ClassAccessWidenFileTransformer();
		try (
			FileSystemUtil.Delegate originalClient = FileSystemUtil.getJarFileSystem(clientOriginalPath);
			FileSystemUtil.Delegate modifiedClient = FileSystemUtil.getJarFileSystem(clientModifiedPath);
			FileSystemUtil.Delegate outputClient = FileSystemUtil.getJarFileSystem(clientOutputPath, true);
			Stream<Path> modifiedClientFileStream = Files.list(modifiedClient.getRoot());
			Stream<Path> originalClientFileStream = Files.list(originalClient.getRoot());
		) {
			for (Path modifiedPath : modifiedClientFileStream.toList()) {
				Path outputPath = outputClient.getRoot().resolve(modifiedClient.getRoot().relativize(modifiedPath));
				if (modifiedPath.getFileName().toString().equals("META-INF") && Files.exists(modifiedPath.resolve("MANIFEST.MF"))) {
					continue;
				}
				if (Files.isRegularFile(modifiedPath)) {
					if (classFileAccessWidenerTransform.shouldTransform(modifiedPath)) {
						Files.write(outputPath, classFileAccessWidenerTransform.transform(modifiedPath, Files.readAllBytes(modifiedPath)), StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
					} else {
						Files.copy(modifiedPath, outputPath, StandardCopyOption.REPLACE_EXISTING);
					}
				} else {
					MiscHelper.copyLargeDir(modifiedPath, outputPath, classFileAccessWidenerTransform);
				}
			}
			for (Path modifiedPath : originalClientFileStream.toList()) {
				Path outputPath = outputClient.getRoot().resolve(originalClient.getRoot().relativize(modifiedPath));
				if (modifiedPath.getFileName().toString().equals("META-INF")) {
					Files.createDirectories(outputPath);
					Path manifestFile = outputPath.resolve("MANIFEST.MF");
					Files.writeString(manifestFile, "Manifest-Version: 1.0\r\n", StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING);
					continue;
				}
				if (Files.isRegularFile(modifiedPath) && !modifiedPath.getFileName().toString().endsWith(".class")) {
					Files.copy(modifiedPath, outputPath, StandardCopyOption.REPLACE_EXISTING);
				} else if (Files.isDirectory(modifiedPath) && !Files.exists(outputPath)) {
					MiscHelper.copyLargeDirExceptNoFileExt(modifiedPath, outputPath, List.of(), Set.of("class"));
				}
			}
		} catch (Exception e) {
			Files.deleteIfExists(clientOutputPath);
			throw e;
		}
		return new StepOutput<>(StepStatus.SUCCESS, results);
	}

	private byte[] transformClassToPublicAccess(byte[] classFileContent) {
		ClassReader reader = new ClassReader(classFileContent);
		ClassNode classNode = new ClassNode(Opcodes.ASM9);
		reader.accept(classNode, 0);

		classNode.access = ensurePublic(classNode.access);
		for (FieldNode field : classNode.fields) {
			field.access = ensurePublic(field.access);
		}
		for (MethodNode method : classNode.methods) {
			method.access = ensurePublic(method.access);
		}
		for (InnerClassNode innerClass : classNode.innerClasses) {
			innerClass.access = ensurePublic(innerClass.access);
		}

		ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES);
		classNode.accept(writer);
		return writer.toByteArray();
	}

	private static int ensurePublic(int access) {
		if ((access & Opcodes.ACC_PUBLIC) != 0 || (access & Opcodes.ACC_PRIVATE) != 0) {
			return access;
		}
		return (access & ~Opcodes.ACC_PROTECTED) | Opcodes.ACC_PUBLIC;
	}

	public record Inputs(Optional<StorageKey> clientJar) implements StepInput {
	}
}
